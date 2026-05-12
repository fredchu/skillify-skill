"""Slot A adapter backed by Anthropic Opus."""

from __future__ import annotations

import os
from pathlib import Path

from .base import SlotScore, build_eval_prompt, parse_score_json


class AnthropicSlotA:
    SLOT = "A"
    NAME = "anthropic"
    DEFAULT_MODEL = "claude-opus-4-7"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("SKILLIFY_ANTHROPIC_MODEL") or self.DEFAULT_MODEL

    @classmethod
    def is_available(cls) -> bool:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        import anthropic

        client = anthropic.Anthropic()
        prompt = build_eval_prompt(skill_path.read_text(encoding="utf-8"), task_description)
        response = client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        scores, improvements = parse_score_json(raw)
        return SlotScore(
            slot=self.SLOT,
            model=self.model,
            scores=scores,
            improvements=improvements,
            raw_response=raw,
        )
