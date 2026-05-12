"""Slot adapters for cross-modal skill evaluation."""

from .base import SlotAdapter, SlotScore, ScoreParseError, build_eval_prompt, parse_score_json
from .slot_a_anthropic import AnthropicSlotA
from .slot_b_codex_dispatch import CodexDispatchSlotB
from .slot_b_gemini import GeminiSlotB
from .slot_b_openai import OpenAISlotB
from .slot_b_raw_codex import RawCodexSlotB

__all__ = [
    "AnthropicSlotA",
    "CodexDispatchSlotB",
    "GeminiSlotB",
    "OpenAISlotB",
    "RawCodexSlotB",
    "ScoreParseError",
    "SlotAdapter",
    "SlotScore",
    "build_eval_prompt",
    "parse_score_json",
]
