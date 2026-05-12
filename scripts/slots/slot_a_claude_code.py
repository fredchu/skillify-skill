"""Slot A adapter — invokes Claude Code via subprocess `claude --print`.

This is the CLI fallback path for the Python adapter. Both this path and
the LLM-driven Agent-tool path (described in SKILL.md Phase 3) bill against
the user's Claude Code subscription, NOT the per-token Anthropic API.

When invoked from inside a CC main session, the SKILL.md instruction
prefers the Agent tool over this subprocess path (faster, no extra CLI
spawn). When invoked from a non-CC shell (e.g. user runs `python3 -m
scripts.cross_modal_eval ./SKILL.md` directly), this subprocess adapter
is the path that runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .base import ScoreParseError, SlotScore, build_eval_prompt, parse_score_json


class ClaudeCodeSlotA:
    SLOT = "A"
    NAME = "claude_code"
    DEFAULT_MODEL = "claude-code-cli"
    DEFAULT_TIMEOUT_SEC = 300

    def __init__(self, claude_binary: str | None = None, timeout_sec: int | None = None):
        self.claude_binary = claude_binary or os.getenv("SKILLIFY_CLAUDE_BIN") or "claude"
        self.timeout_sec = timeout_sec or self.DEFAULT_TIMEOUT_SEC

    @classmethod
    def is_available(cls) -> bool:
        """True iff `claude` or SKILLIFY_CLAUDE_BIN is on PATH."""

        binary = os.getenv("SKILLIFY_CLAUDE_BIN") or "claude"
        return shutil.which(binary) is not None

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        """Run `claude --print`, parse JSON, and return a SlotScore."""

        prompt = build_eval_prompt(skill_path.read_text(encoding="utf-8"), task_description)
        try:
            result = subprocess.run(
                [self.claude_binary, "--print", prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"claude CLI timed out after {self.timeout_sec}s") from exc

        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI returned non-zero exit {result.returncode}: "
                f"stderr={result.stderr[:500]!r}"
            )

        raw = result.stdout
        scores, improvements = parse_score_json(raw)
        return SlotScore(
            slot=self.SLOT,
            model=self.DEFAULT_MODEL,
            scores=scores,
            improvements=improvements,
            raw_response=raw,
        )


__all__ = ["ClaudeCodeSlotA", "ScoreParseError"]
