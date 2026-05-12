"""Slot B adapter backed by raw `codex exec`."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import SlotScore, build_eval_prompt, parse_score_json


class RawCodexSlotB:
    SLOT = "B"
    NAME = "raw_codex"
    DEFAULT_MODEL = "codex-cli/gpt-5"
    TIMEOUT_SECONDS = 300

    def __init__(self, model: str | None = None):
        self.model = model or self.DEFAULT_MODEL

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("codex") is not None

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        prompt = build_eval_prompt(skill_path.read_text(encoding="utf-8"), task_description)
        try:
            result = subprocess.run(
                ["codex", "exec", "--full-auto"],
                input=prompt,
                text=True,
                capture_output=True,
                timeout=self.TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("codex exec timed out") from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"codex exec failed with exit code {result.returncode}: {detail}")

        raw = result.stdout
        scores, improvements = parse_score_json(raw)
        return SlotScore(
            slot=self.SLOT,
            model=self.model,
            scores=scores,
            improvements=improvements,
            raw_response=raw,
        )
