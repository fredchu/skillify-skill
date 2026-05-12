from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.slots.base import ScoreParseError, SlotScore
from scripts.slots.slot_a_claude_code import ClaudeCodeSlotA


VALID_JSON = """```json
{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": ["tighten triggers"]}
```"""


def test_is_available_no_binary() -> None:
    with patch("scripts.slots.slot_a_claude_code.shutil.which", return_value=None):
        assert ClaudeCodeSlotA.is_available() is False


def test_is_available_present() -> None:
    with patch(
        "scripts.slots.slot_a_claude_code.shutil.which",
        return_value="/usr/local/bin/claude",
    ):
        assert ClaudeCodeSlotA.is_available() is True


def test_is_available_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLIFY_CLAUDE_BIN", "claude-custom")
    with patch(
        "scripts.slots.slot_a_claude_code.shutil.which",
        return_value="/usr/local/bin/claude-custom",
    ) as mock_which:
        assert ClaudeCodeSlotA.is_available() is True

    mock_which.assert_called_once_with("claude-custom")


def test_score_happy_path(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=["claude", "--print", "prompt"],
        returncode=0,
        stdout=VALID_JSON,
        stderr="",
    )

    with patch("scripts.slots.slot_a_claude_code.subprocess.run", return_value=completed):
        result = ClaudeCodeSlotA().score(skill_path, "task")

    assert isinstance(result, SlotScore)
    assert result.slot == "A"
    assert result.model == "claude-code-cli"
    assert result.scores["goal"] == 8
    assert result.improvements == ["tighten triggers"]


def test_score_invalid_json_raises_score_parse_error(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=["claude", "--print", "prompt"],
        returncode=0,
        stdout="not json",
        stderr="",
    )

    with patch("scripts.slots.slot_a_claude_code.subprocess.run", return_value=completed):
        with pytest.raises(ScoreParseError):
            ClaudeCodeSlotA().score(skill_path, "task")


def test_score_subprocess_nonzero_raises_runtime_error(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=["claude", "--print", "prompt"],
        returncode=2,
        stdout="",
        stderr="quota exhausted",
    )

    with patch("scripts.slots.slot_a_claude_code.subprocess.run", return_value=completed):
        with pytest.raises(RuntimeError, match="quota exhausted"):
            ClaudeCodeSlotA().score(skill_path, "task")


def test_score_timeout_raises_runtime_error(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")

    with patch(
        "scripts.slots.slot_a_claude_code.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["claude"], timeout=300),
    ):
        with pytest.raises(RuntimeError, match="timed out"):
            ClaudeCodeSlotA().score(skill_path, "task")


def test_score_passes_prompt_to_subprocess(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=["claude", "--print", "prompt"],
        returncode=0,
        stdout=VALID_JSON,
        stderr="",
    )

    with patch(
        "scripts.slots.slot_a_claude_code.subprocess.run",
        return_value=completed,
    ) as mock_run:
        ClaudeCodeSlotA().score(skill_path, "task")

    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert args[0:2] == ["claude", "--print"]
    assert "skill text" in args[2]
    assert "task" in args[2]
    assert mock_run.call_args.kwargs == {
        "capture_output": True,
        "text": True,
        "timeout": 300,
        "check": False,
    }


def test_default_timeout_300_seconds() -> None:
    assert ClaudeCodeSlotA().timeout_sec == 300


def test_custom_timeout() -> None:
    assert ClaudeCodeSlotA(timeout_sec=60).timeout_sec == 60
