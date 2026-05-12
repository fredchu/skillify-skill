"""Slot B adapter backed by the codex-dispatch skill."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import SlotScore, build_eval_prompt, parse_score_json


class CodexDispatchSlotB:
    SLOT = "B"
    NAME = "codex_dispatch"
    DEFAULT_MODEL = "codex-dispatch/gpt-5"
    DISPATCH_SCRIPT = Path.home() / ".claude/skills/codex-dispatch/scripts/codex_dispatch_role.py"
    TIMEOUT_SECONDS = 300

    def __init__(self, model: str | None = None):
        self.model = model or self.DEFAULT_MODEL

    @classmethod
    def is_available(cls) -> bool:
        return cls.DISPATCH_SCRIPT.exists() and shutil.which("codex") is not None

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        prompt = build_eval_prompt(skill_path.read_text(encoding="utf-8"), task_description)
        with tempfile.TemporaryDirectory(prefix="skillify-codex-dispatch-") as tmp_dir:
            task_path = Path(tmp_dir) / "task.md"
            task_path.write_text(_build_task_packet(prompt), encoding="utf-8")

            output_root = Path(tmp_dir) / "runs"
            try:
                result = subprocess.run(
                    [
                        "python3", str(self.DISPATCH_SCRIPT),
                        "--task", str(task_path),
                        "--output-dir", str(output_root),
                    ],
                    text=True,
                    capture_output=True,
                    timeout=self.TIMEOUT_SECONDS,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError("codex-dispatch timed out") from exc

            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(
                    f"codex-dispatch failed with exit code {result.returncode}: {detail}"
                )

            raw = _read_dispatch_output(Path(tmp_dir), result.stdout)

        scores, improvements = parse_score_json(raw)
        return SlotScore(
            slot=self.SLOT,
            model=self.model,
            scores=scores,
            improvements=improvements,
            raw_response=raw,
        )


def _build_task_packet(prompt: str) -> str:
    return f"""MODE: reviewer
WORKDIR: {Path.cwd()}
OBJECTIVE: Evaluate the provided skill and return only the requested JSON scores. Read the skill content embedded in PROMPT; do not load any other files.

WRITE SCOPE:
- none

NON-GOALS:
- Do not modify any files.
- Do not include commentary outside the strict JSON output.

VERIFICATION:
- The deliverable JSON must contain a `scores` object with exactly 5 integer keys (goal, depth, specificity, robustness, trigger_clarity) each in [0,10], plus an `improvements` list of strings.

DELIVERABLE:
- Strict JSON object: {{"scores": {{"goal": int, "depth": int, "specificity": int, "robustness": int, "trigger_clarity": int}}, "improvements": ["..."]}}
- No prose outside the JSON. Fenced code block is acceptable.

PROMPT:
{prompt}
"""


def _read_dispatch_output(tmp_path: Path, stdout: str) -> str:
    """Read codex-dispatch envelope and extract the reviewer model's deliverable.

    Resolution order:
    1. codex_dispatch_role.py prints the run_dir path on stdout (last line).
    2. Read result.json from that run_dir; the model's strict-JSON deliverable
       is nested inside envelope.summary as a stringified JSON object.
    3. Fall back to result.md (rarely needed; envelope.summary is canonical).
    4. Fall back to raw stdout (only if no artifacts found at all).
    """
    import json as _json

    stdout_lines = stdout.strip().splitlines() if stdout.strip() else []
    stdout_run_dir = Path(stdout_lines[-1]) if stdout_lines else None
    if not (stdout_run_dir and stdout_run_dir.is_dir()):
        return stdout

    result_json_path = stdout_run_dir / "result.json"
    if result_json_path.exists():
        content = result_json_path.read_text(encoding="utf-8")
        try:
            envelope = _json.loads(content)
        except _json.JSONDecodeError:
            return content  # malformed envelope — let parse_score_json complain
        if not isinstance(envelope, dict):
            return content
        summary = envelope.get("summary")
        if isinstance(summary, str) and ("{" in summary or "scores" in summary):
            return summary
        return content  # envelope present but summary not parseable — let caller raise

    result_md_path = stdout_run_dir / "result.md"
    if result_md_path.exists():
        return result_md_path.read_text(encoding="utf-8")

    return stdout
