"""Slot B adapter backed by the OpenAI SDK."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import SlotScore, build_eval_prompt, parse_score_json


class OpenAISlotB:
    SLOT = "B"
    NAME = "openai"
    DEFAULT_MODEL = "gpt-5"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("SKILLIFY_OPENAI_MODEL") or self.DEFAULT_MODEL

    @classmethod
    def is_available(cls) -> bool:
        if not os.getenv("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
        except ImportError:
            return False
        return True

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        import openai

        client = openai.OpenAI()
        prompt = build_eval_prompt(skill_path.read_text(encoding="utf-8"), task_description)
        response = client.responses.create(
            model=self.model,
            input=prompt,
            max_output_tokens=4000,
        )
        raw = _extract_openai_text(response)
        scores, improvements = parse_score_json(raw)
        return SlotScore(
            slot=self.SLOT,
            model=self.model,
            scores=scores,
            improvements=improvements,
            raw_response=raw,
        )


def _extract_openai_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

    output = getattr(response, "output", None)
    if output:
        first = output[0]
        content = getattr(first, "content", None)
        if content:
            text = getattr(content[0], "text", None)
            if isinstance(text, str):
                return text

    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content

    raise ValueError("OpenAI response did not contain text output")
