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

            try:
                result = subprocess.run(
                    ["python3", str(self.DISPATCH_SCRIPT), "--task", str(task_path)],
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
    # codex_dispatch_role.py writes its envelope at <workdir>/.codex-dispatch/runs/<id>/.
    # The path is printed on stdout. The reviewer model's strict-JSON deliverable
    # appears nested inside result.json's `summary` string (codex envelope wraps it).
    import json as _json

    for name in ("result.json", "result.md"):
        candidate = tmp_path / name
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    stdout_run_dir = Path(stdout.strip().splitlines()[-1]) if stdout.strip() else None
    if not (stdout_run_dir and stdout_run_dir.is_dir()):
        return stdout

    result_json_path = stdout_run_dir / "result.json"
    if result_json_path.exists():
        content = result_json_path.read_text(encoding="utf-8")
        try:
            envelope = _json.loads(content)
            # Reviewer mode: model deliverable JSON nested in envelope.summary.
            summary = envelope.get("summary", "")
            if summary.strip().startswith("{") or "scores" in summary:
                return summary
        except (_json.JSONDecodeError, AttributeError):
            pass
        return content

    result_md_path = stdout_run_dir / "result.md"
    if result_md_path.exists():
        return result_md_path.read_text(encoding="utf-8")

    return stdout
