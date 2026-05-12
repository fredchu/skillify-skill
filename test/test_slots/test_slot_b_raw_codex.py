from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.slots.base import SlotScore
from scripts.slots.slot_b_raw_codex import RawCodexSlotB


VALID_JSON = """{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": ["tighten triggers"]}"""


def test_is_available_no_codex() -> None:
    with patch("scripts.slots.slot_b_raw_codex.shutil.which", return_value=None):
        assert RawCodexSlotB.is_available() is False


def test_is_available_present() -> None:
    with patch("scripts.slots.slot_b_raw_codex.shutil.which", return_value="/usr/bin/codex"):
        assert RawCodexSlotB.is_available() is True


def test_score_happy_path(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=["codex", "exec", "--full-auto"],
        returncode=0,
        stdout=VALID_JSON,
        stderr="",
    )

    with patch("scripts.slots.slot_b_raw_codex.subprocess.run", return_value=completed):
        result = RawCodexSlotB().score(skill_path, "task")

    assert isinstance(result, SlotScore)
    assert result.slot == "B"
    assert result.model == "codex-cli/gpt-5"
    assert result.scores["goal"] == 8
    assert result.improvements == ["tighten triggers"]


def test_score_timeout_raises(tmp_path: Path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")

    with patch(
        "scripts.slots.slot_b_raw_codex.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=300),
    ):
        with pytest.raises(TimeoutError, match="timed out"):
            RawCodexSlotB().score(skill_path, "task")
