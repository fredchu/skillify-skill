from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from scripts.slots.base import ScoreParseError, SlotScore
from scripts.slots.slot_b_openai import OpenAISlotB


VALID_JSON = """```json
{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": ["tighten triggers"]}
```"""


def test_is_available_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert OpenAISlotB.is_available() is False


def test_is_available_no_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", None)

    assert OpenAISlotB.is_available() is False


def test_is_available_both_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "openai", types.ModuleType("openai"))

    assert OpenAISlotB.is_available() is True


def test_score_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    fake_module = types.ModuleType("openai")
    response = types.SimpleNamespace(output_text=VALID_JSON)
    client = types.SimpleNamespace(
        responses=types.SimpleNamespace(create=lambda **_: response)
    )
    fake_module.OpenAI = lambda: client
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    result = OpenAISlotB().score(skill_path, "task")

    assert isinstance(result, SlotScore)
    assert result.slot == "B"
    assert result.model == "gpt-5"
    assert result.scores["goal"] == 8
    assert result.improvements == ["tighten triggers"]


def test_score_invalid_json_raises_score_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    fake_module = types.ModuleType("openai")
    response = types.SimpleNamespace(output_text="not json")
    client = types.SimpleNamespace(responses=types.SimpleNamespace(create=lambda **_: response))
    fake_module.OpenAI = lambda: client
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    with pytest.raises(ScoreParseError):
        OpenAISlotB().score(skill_path, "task")


def test_default_model_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLIFY_OPENAI_MODEL", raising=False)

    assert OpenAISlotB().model == "gpt-5"


def test_env_override_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLIFY_OPENAI_MODEL", "gpt-custom")

    assert OpenAISlotB().model == "gpt-custom"
