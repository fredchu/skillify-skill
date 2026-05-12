"""Slot B adapter backed by the Gemini SDK."""

from __future__ import annotations

import os
from pathlib import Path

from .base import SlotScore, build_eval_prompt, parse_score_json


class GeminiSlotB:
    SLOT = "B"
    NAME = "gemini"
    DEFAULT_MODEL = "gemini-1.5-pro"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("SKILLIFY_GEMINI_MODEL") or self.DEFAULT_MODEL

    @classmethod
    def is_available(cls) -> bool:
        if not (os.getenv("GOOGLE_GENERATIVE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
            return False
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            return False
        return True

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        import google.generativeai as genai

        api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(self.model)
        prompt = build_eval_prompt(skill_path.read_text(encoding="utf-8"), task_description)
        response = model.generate_content(prompt)
        raw = response.text
        scores, improvements = parse_score_json(raw)
        return SlotScore(
            slot=self.SLOT,
            model=self.model,
            scores=scores,
            improvements=improvements,
            raw_response=raw,
        )
