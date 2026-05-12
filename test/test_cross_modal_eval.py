from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import cross_modal_eval
from scripts.receipt import compute_sha8
from scripts.slots import SlotScore


def _skill(path: Path) -> Path:
    skill_path = path / "SKILL.md"
    skill_path.write_text(
        """---
name: demo
description: |
  Use when the user says "demo this" or "audit demo".
---

# Demo
""",
        encoding="utf-8",
    )
    return skill_path


def _slot_score(slot: str, model: str, value: int) -> SlotScore:
    return SlotScore(
        slot=slot,
        model=model,
        scores={
            "goal": value,
            "depth": value,
            "specificity": value,
            "robustness": value,
            "trigger_clarity": value,
        },
        improvements=["tighten coverage"],
        raw_response="{}",
    )


class PassingSlotA:
    SLOT = "A"
    NAME = "slot-a"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        return _slot_score("A", "a-model", 8)


class PassingSlotB:
    SLOT = "B"
    NAME = "slot-b"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        return _slot_score("B", "b-model", 8)


class FailingSlotB(PassingSlotB):
    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        return _slot_score("B", "b-model", 5)


def test_detect_available_slots_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cross_modal_eval.AnthropicSlotA, "is_available", classmethod(lambda cls: False))

    assert cross_modal_eval.detect_available_slots() == (None, None)


def test_detect_available_slots_only_slot_a(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cross_modal_eval.AnthropicSlotA, "is_available", classmethod(lambda cls: True))
    for slot_b in cross_modal_eval.SLOT_B_FALLBACKS:
        monkeypatch.setattr(slot_b, "is_available", classmethod(lambda cls: False))

    assert cross_modal_eval.detect_available_slots() == (cross_modal_eval.AnthropicSlotA, None)


def test_detect_available_slots_full(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cross_modal_eval.AnthropicSlotA, "is_available", classmethod(lambda cls: True))
    monkeypatch.setattr(
        cross_modal_eval.CodexDispatchSlotB,
        "is_available",
        classmethod(lambda cls: True),
    )

    assert cross_modal_eval.detect_available_slots() == (
        cross_modal_eval.AnthropicSlotA,
        cross_modal_eval.CodexDispatchSlotB,
    )


def test_run_cycle_pass(tmp_path: Path) -> None:
    result = cross_modal_eval.run_cycle(
        _skill(tmp_path),
        "task",
        PassingSlotA(),
        PassingSlotB(),
    )

    assert result["verdict"] == "pass"
    assert result["aggregate"]["verdict"] == "pass"


def test_run_cycle_fail(tmp_path: Path) -> None:
    result = cross_modal_eval.run_cycle(
        _skill(tmp_path),
        "task",
        PassingSlotA(),
        FailingSlotB(),
    )

    assert result["verdict"] == "fail"


def test_evaluate_writes_receipt_on_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    skill_path = _skill(tmp_path)
    receipt_dir = tmp_path / "receipts"
    monkeypatch.setattr(
        cross_modal_eval,
        "detect_available_slots",
        lambda: (PassingSlotA, PassingSlotB),
    )

    result = cross_modal_eval.evaluate(
        skill_path,
        "task",
        cycles=2,
        base_dir=receipt_dir,
    )

    assert result["final_verdict"] == "pass"
    assert result["cycles_run"] == 1
    receipt_path = Path(result["receipt_path"])
    assert receipt_path.exists()
    assert compute_sha8(skill_path) in receipt_path.name
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["skill_sha8"] == compute_sha8(skill_path)


def test_evaluate_returns_unavailable_when_no_slots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cross_modal_eval, "detect_available_slots", lambda: (None, None))

    result = cross_modal_eval.evaluate(_skill(tmp_path), "task")

    assert result["final_verdict"] == "unavailable"
    assert "reason" in result


def test_main_cli_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    skill_path = _skill(tmp_path)
    monkeypatch.setattr(
        cross_modal_eval,
        "evaluate",
        lambda *_, **__: {"final_verdict": "pass", "cycles_run": 1},
    )
    assert cross_modal_eval.main([str(skill_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["final_verdict"] == "pass"

    monkeypatch.setattr(
        cross_modal_eval,
        "evaluate",
        lambda *_, **__: {"final_verdict": "split", "cycles_run": 1},
    )
    assert cross_modal_eval.main([str(skill_path), "--json"]) == 1

    monkeypatch.setattr(
        cross_modal_eval,
        "evaluate",
        lambda *_, **__: {"final_verdict": "unavailable", "reason": "no slots"},
    )
    assert cross_modal_eval.main([str(skill_path), "--json"]) == 2
