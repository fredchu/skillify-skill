from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from scripts.slots.base import ScoreParseError, SlotScore
from scripts.slots.slot_a_anthropic import AnthropicSlotA


VALID_JSON = """```json
{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": ["tighten triggers"]}
```"""


def test_is_available_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert AnthropicSlotA.is_available() is False


def test_is_available_no_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "anthropic", None)

    assert AnthropicSlotA.is_available() is False


def test_is_available_both_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "anthropic", types.ModuleType("anthropic"))

    assert AnthropicSlotA.is_available() is True


def test_score_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    fake_module = types.ModuleType("anthropic")
    response = types.SimpleNamespace(content=[types.SimpleNamespace(text=VALID_JSON)])
    create = lambda **_: response
    client = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))
    fake_module.Anthropic = lambda: client
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    result = AnthropicSlotA().score(skill_path, "task")

    assert isinstance(result, SlotScore)
    assert result.slot == "A"
    assert result.model == "claude-opus-4-7"
    assert result.scores["goal"] == 8
    assert result.improvements == ["tighten triggers"]


def test_score_invalid_json_raises_score_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    fake_module = types.ModuleType("anthropic")
    response = types.SimpleNamespace(content=[types.SimpleNamespace(text="not json")])
    client = types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **_: response))
    fake_module.Anthropic = lambda: client
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    with pytest.raises(ScoreParseError):
        AnthropicSlotA().score(skill_path, "task")


def test_default_model_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLIFY_ANTHROPIC_MODEL", raising=False)

    assert AnthropicSlotA().model == "claude-opus-4-7"


def test_env_override_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLIFY_ANTHROPIC_MODEL", "claude-custom")

    assert AnthropicSlotA().model == "claude-custom"
