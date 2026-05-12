from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from scripts.slots.base import ScoreParseError, SlotScore
from scripts.slots.slot_b_gemini import GeminiSlotB


VALID_JSON = """```json
{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": ["tighten triggers"]}
```"""


def _install_fake_gemini(monkeypatch: pytest.MonkeyPatch, text: str = VALID_JSON) -> None:
    google_module = types.ModuleType("google")
    google_module.__path__ = []
    genai_module = types.ModuleType("google.generativeai")
    genai_module.configure = lambda **_: None
    genai_module.GenerativeModel = lambda _: types.SimpleNamespace(
        generate_content=lambda __: types.SimpleNamespace(text=text)
    )
    google_module.generativeai = genai_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.generativeai", genai_module)


def test_is_available_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_GENERATIVE_AI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    assert GeminiSlotB.is_available() is False


def test_is_available_no_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_GENERATIVE_AI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "google.generativeai", None)

    assert GeminiSlotB.is_available() is False


def test_is_available_both_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_GENERATIVE_AI_API_KEY", "test-key")
    _install_fake_gemini(monkeypatch)

    assert GeminiSlotB.is_available() is True


def test_score_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GOOGLE_GENERATIVE_AI_API_KEY", "test-key")
    _install_fake_gemini(monkeypatch)
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")

    result = GeminiSlotB().score(skill_path, "task")

    assert isinstance(result, SlotScore)
    assert result.slot == "B"
    assert result.model == "gemini-1.5-pro"
    assert result.scores["goal"] == 8
    assert result.improvements == ["tighten triggers"]


def test_score_invalid_json_raises_score_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("GOOGLE_GENERATIVE_AI_API_KEY", "test-key")
    _install_fake_gemini(monkeypatch, text="not json")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")

    with pytest.raises(ScoreParseError):
        GeminiSlotB().score(skill_path, "task")


def test_default_model_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLIFY_GEMINI_MODEL", raising=False)

    assert GeminiSlotB().model == "gemini-1.5-pro"


def test_env_override_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLIFY_GEMINI_MODEL", "gemini-custom")

    assert GeminiSlotB().model == "gemini-custom"
