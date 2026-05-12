from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import audit
from scripts.receipt import write_receipt


def _write_skill(
    root: Path,
    *,
    description: str = 'Use when the user says "skillify this" or "audit this skill".',
    body: str = "## Output\n\nNo persistent writes.\n",
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    skill_path = root / "SKILL.md"
    skill_path.write_text(
        f"""---
name: demo
description: |
  {description}
---

# Demo

{body}
""",
        encoding="utf-8",
    )
    return skill_path


def _add_script(root: Path, name: str = "foo.py", text: str = "VALUE = 1\n") -> None:
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / name).write_text(text, encoding="utf-8")


def _add_test(root: Path, name: str = "test_foo.py", text: str = "def test_ok():\n    assert True\n") -> None:
    test_dir = root / "test"
    test_dir.mkdir(exist_ok=True)
    (test_dir / name).write_text(text, encoding="utf-8")


def _patch_receipt_dir(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    receipts = root / "receipts"

    def receipt_dir() -> Path:
        receipts.mkdir(parents=True, exist_ok=True)
        return receipts

    monkeypatch.setattr(audit.receipt, "receipt_dir", receipt_dir)
    return receipts


def test_audit_minimal_skill_passes(tmp_path: Path, monkeypatch) -> None:
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path, name="test_e2e_demo.py")

    # Hermetic: pin Slot detection to (None, None) so cross_modal_eval is NA
    # (test should not depend on whether `claude`/`codex` is on PATH).
    monkeypatch.setattr(
        audit.cross_modal_eval,
        "detect_available_slots",
        lambda: (None, None),
    )

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["verdict"] == "properly skilled"
    assert result["score"] == "6/6"


def test_audit_missing_skill_md_returns_needs_skillify(tmp_path: Path) -> None:
    result = audit.audit_skill(tmp_path / "SKILL.md", project_root=tmp_path)

    assert result["verdict"] == "needs skillify"
    assert result["items"]["skill_md_present"]["status"] == "fail"


def test_audit_close_when_one_missing(tmp_path: Path) -> None:
    skill_path = _write_skill(tmp_path)
    _add_test(tmp_path, name="test_e2e_demo.py")

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["verdict"] == "close"
    assert result["items"]["code_present"]["status"] == "fail"


def test_audit_cross_modal_na_when_no_slots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit.cross_modal_eval,
        "detect_available_slots",
        lambda: (None, None),
    )
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path, name="test_e2e_demo.py")

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["items"]["cross_modal_eval"]["status"] == "na"
    assert result["verdict"] == "properly skilled"


def test_audit_cross_modal_pass_when_receipt_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit.cross_modal_eval,
        "detect_available_slots",
        lambda: (object, object),
    )
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path, name="test_e2e_demo.py")
    monkeypatch.setattr(audit.receipt, "find_current_receipt", lambda slug, path: tmp_path / "receipt.json")

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["items"]["cross_modal_eval"]["status"] == "pass"
    assert result["verdict"] == "properly skilled"


def test_audit_cross_modal_fail_when_slots_but_no_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit.cross_modal_eval,
        "detect_available_slots",
        lambda: (object, object),
    )
    monkeypatch.setattr(audit.receipt, "find_current_receipt", lambda slug, path: None)
    monkeypatch.setattr(audit.receipt, "list_receipts", lambda slug: [])
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path, name="test_e2e_demo.py")

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["items"]["cross_modal_eval"]["status"] == "fail"
    assert result["verdict"] == "close"
    assert result["score"] == "6/7"


def test_audit_cross_modal_status_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit.cross_modal_eval,
        "detect_available_slots",
        lambda: (object, object),
    )
    _patch_receipt_dir(monkeypatch, tmp_path)
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path)
    write_receipt("demo", skill_path, {"verdict": "pass"})
    skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["cross_modal_status"] == "stale"


def test_audit_e2e_test_pass_when_e2e_file_present(tmp_path: Path) -> None:
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path, name="test_e2e_foo.py")

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["items"]["e2e_test"]["status"] == "pass"


def test_audit_e2e_test_pass_when_e2e_marker_present(tmp_path: Path) -> None:
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(
        tmp_path,
        text="import pytest\n\n@pytest.mark.e2e\ndef test_ok():\n    assert True\n",
    )

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["items"]["e2e_test"]["status"] == "pass"


def test_audit_e2e_test_fail_when_no_e2e(tmp_path: Path) -> None:
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path)

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["items"]["e2e_test"]["status"] == "fail"
    assert result["verdict"] == "close"


def test_audit_score_format_with_na(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        audit.cross_modal_eval,
        "detect_available_slots",
        lambda: (None, None),
    )
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path, name="test_e2e_demo.py")

    result = audit.audit_skill(skill_path, project_root=tmp_path)

    assert result["score"] == "6/6"


def test_main_cli_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    skill_path = _write_skill(tmp_path)
    _add_script(tmp_path)
    _add_test(tmp_path)
    assert audit.main([str(skill_path), "--project-root", str(tmp_path), "--json"]) == 0
    close_result = json.loads(capsys.readouterr().out)
    assert close_result["verdict"] == "close"

    assert audit.main([str(tmp_path / "missing.md"), "--project-root", str(tmp_path), "--json"]) == 1
    needs_result = json.loads(capsys.readouterr().out)
    assert needs_result["verdict"] == "needs skillify"
