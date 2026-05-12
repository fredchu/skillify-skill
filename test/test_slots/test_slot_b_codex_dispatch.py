from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.slots.base import SlotScore
from scripts.slots.slot_b_codex_dispatch import CodexDispatchSlotB


VALID_JSON = """{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": ["tighten triggers"]}"""


def test_is_available_no_codex_binary(tmp_path: Path) -> None:
    script = tmp_path / "codex_dispatch_role.py"
    script.write_text("# dispatch", encoding="utf-8")

    with (
        patch.object(CodexDispatchSlotB, "DISPATCH_SCRIPT", script),
        patch("scripts.slots.slot_b_codex_dispatch.shutil.which", return_value=None),
    ):
        assert CodexDispatchSlotB.is_available() is False


def test_is_available_no_dispatch_script(tmp_path: Path) -> None:
    script = tmp_path / "missing.py"

    with (
        patch.object(CodexDispatchSlotB, "DISPATCH_SCRIPT", script),
        patch("scripts.slots.slot_b_codex_dispatch.shutil.which", return_value="/usr/bin/codex"),
    ):
        assert CodexDispatchSlotB.is_available() is False


def test_is_available_present_returns_true(tmp_path: Path) -> None:
    script = tmp_path / "codex_dispatch_role.py"
    script.write_text("# dispatch", encoding="utf-8")

    with (
        patch.object(CodexDispatchSlotB, "DISPATCH_SCRIPT", script),
        patch("scripts.slots.slot_b_codex_dispatch.shutil.which", return_value="/usr/bin/codex"),
    ):
        assert CodexDispatchSlotB.is_available() is True


def test_score_happy_path(tmp_path: Path) -> None:
    script = tmp_path / "codex_dispatch_role.py"
    script.write_text("# dispatch", encoding="utf-8")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=["python3", str(script), "--task", "task.md"],
        returncode=0,
        stdout=VALID_JSON,
        stderr="",
    )

    with (
        patch.object(CodexDispatchSlotB, "DISPATCH_SCRIPT", script),
        patch("scripts.slots.slot_b_codex_dispatch.subprocess.run", return_value=completed),
    ):
        result = CodexDispatchSlotB().score(skill_path, "task")

    assert isinstance(result, SlotScore)
    assert result.slot == "B"
    assert result.model == "codex-dispatch/gpt-5"
    assert result.scores["goal"] == 8
    assert result.improvements == ["tighten triggers"]


def test_score_subprocess_failure_raises(tmp_path: Path) -> None:
    script = tmp_path / "codex_dispatch_role.py"
    script.write_text("# dispatch", encoding="utf-8")
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("skill text", encoding="utf-8")
    completed = subprocess.CompletedProcess(
        args=["python3", str(script), "--task", "task.md"],
        returncode=1,
        stdout="",
        stderr="dispatch failed",
    )

    with (
        patch.object(CodexDispatchSlotB, "DISPATCH_SCRIPT", script),
        patch("scripts.slots.slot_b_codex_dispatch.subprocess.run", return_value=completed),
    ):
        with pytest.raises(RuntimeError, match="dispatch failed"):
            CodexDispatchSlotB().score(skill_path, "task")
