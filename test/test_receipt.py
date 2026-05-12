from __future__ import annotations

import json
import string

from scripts import receipt
from scripts.receipt import (
    compute_sha8,
    find_current_receipt,
    list_receipts,
    receipt_dir,
    receipt_filename,
    write_receipt,
)


def test_compute_sha8_deterministic(tmp_path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("same content", encoding="utf-8")

    first = compute_sha8(skill_path)
    second = compute_sha8(skill_path)
    assert first == second
    assert len(first) == 8
    assert all(char in string.hexdigits for char in first)

    skill_path.write_text("different content", encoding="utf-8")
    assert compute_sha8(skill_path) != first


def test_write_and_find_roundtrip(tmp_path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("hello", encoding="utf-8")
    eval_data = {"verdict": "pass", "score": 9}

    written = write_receipt("test", skill_path, eval_data, base_dir=tmp_path)
    found = find_current_receipt("test", skill_path, base_dir=tmp_path)

    assert found == written
    expected_sha8 = compute_sha8(skill_path)
    assert written.name == receipt_filename("test", expected_sha8)

    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "v1"
    assert payload["skill_slug"] == "test"
    assert payload["skill_sha8"] == expected_sha8
    assert payload["eval"] == eval_data
    assert isinstance(payload["written_at"], str)


def test_staleness_after_mutation(tmp_path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("original", encoding="utf-8")
    write_receipt("test", skill_path, {"verdict": "pass"}, base_dir=tmp_path)

    skill_path.write_text("mutated", encoding="utf-8")

    assert find_current_receipt("test", skill_path, base_dir=tmp_path) is None


def test_old_receipt_preserved_after_mutation(tmp_path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("original", encoding="utf-8")
    old_receipt = write_receipt("test", skill_path, {"verdict": "pass"}, base_dir=tmp_path)

    skill_path.write_text("mutated", encoding="utf-8")

    assert find_current_receipt("test", skill_path, base_dir=tmp_path) is None
    assert list_receipts("test", base_dir=tmp_path) == [old_receipt]
    assert old_receipt.exists()


def test_two_skills_isolated(tmp_path) -> None:
    skill_path = tmp_path / "SKILL.md"
    skill_path.write_text("shared content", encoding="utf-8")
    a_receipt = write_receipt("a", skill_path, {"verdict": "pass"}, base_dir=tmp_path)
    b_receipt = write_receipt("b", skill_path, {"verdict": "fail"}, base_dir=tmp_path)

    assert find_current_receipt("a", skill_path, base_dir=tmp_path) == a_receipt
    assert find_current_receipt("b", skill_path, base_dir=tmp_path) == b_receipt
    assert list_receipts("a", base_dir=tmp_path) == [a_receipt]


def test_receipt_dir_default_uses_platformdirs(tmp_path, monkeypatch) -> None:
    cache_root = tmp_path / "cache"
    monkeypatch.setattr(
        receipt.platformdirs,
        "user_cache_dir",
        lambda appname: str(cache_root / appname),
    )

    assert receipt_dir() == cache_root / "skillify" / "eval-receipts"


def test_filename_format() -> None:
    assert receipt_filename("my-skill", "1a2b3c4d") == "my-skill-1a2b3c4d.json"
