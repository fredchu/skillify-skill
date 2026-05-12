from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_resolvable import detect_collisions, emit_resolver_md, scan_skills


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_skill(root: Path, name: str, description: str) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(
        f"""---
name: {name}
description: |
  {description}
---

# {name}
""",
        encoding="utf-8",
    )
    return skill_path


def test_scan_finds_skill_md_in_subdirs(tmp_path) -> None:
    _write_skill(tmp_path, "skill-a", 'Use when "alpha task".')
    _write_skill(tmp_path / "sub", "skill-b", 'Use when "beta task".')

    skills = scan_skills([tmp_path])

    assert {skill["name"] for skill in skills} == {"skill-a", "skill-b"}


def test_scan_skips_malformed(tmp_path) -> None:
    _write_skill(tmp_path, "valid", 'Use when "valid task".')
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("name: bad\n", encoding="utf-8")
    yaml_bad_dir = tmp_path / "yaml-bad"
    yaml_bad_dir.mkdir()
    (yaml_bad_dir / "SKILL.md").write_text(
        "---\nname: [bad\n---\n",
        encoding="utf-8",
    )

    skills = scan_skills([tmp_path])

    assert [skill["name"] for skill in skills] == ["valid"]


def test_scan_skips_excluded_dirs(tmp_path) -> None:
    _write_skill(tmp_path / ".codex-dispatch" / "runs", "x", 'Use when "hidden".')

    assert scan_skills([tmp_path]) == []


def test_scan_dedups_same_content(tmp_path) -> None:
    skills_root = tmp_path / "skills"
    cache_root = tmp_path / "plugins" / "cache" / "x" / "skills"
    _write_skill(skills_root, "same", 'Use when "same trigger" or "same task".')
    _write_skill(cache_root, "same", 'Use when "same trigger" or "same task".')

    skills = scan_skills([skills_root, tmp_path / "plugins" / "cache"])

    assert len(skills) == 1
    assert skills[0]["name"] == "same"


def test_synthetic_collision_detected(tmp_path) -> None:
    _write_skill(tmp_path, "one", 'Use when "foo bar" or "baz qux".')
    _write_skill(tmp_path, "two", 'Trigger: "foo bar", "baz qux".')
    skills = scan_skills([tmp_path])

    collisions = detect_collisions(skills)

    assert len(collisions) == 1
    assert set(collisions[0]["skills"]) == {"one", "two"}
    assert set(collisions[0]["shared_triggers"]) >= {"foo bar", "baz qux"}
    assert collisions[0]["overlap_count"] >= 2


def test_no_collision_when_distinct(tmp_path) -> None:
    _write_skill(tmp_path, "one", 'Use when "alpha task".')
    _write_skill(tmp_path, "two", 'Use when "omega task".')

    collisions = detect_collisions(scan_skills([tmp_path]))

    assert collisions == []


def test_strict_mode_skips_blob_collisions(tmp_path) -> None:
    _write_skill(
        tmp_path,
        "one",
        "Analyze repeated project context and produce stable output.",
    )
    _write_skill(
        tmp_path,
        "two",
        "Summarize repeated project context and produce concise notes.",
    )
    skills = scan_skills([tmp_path])

    assert len(detect_collisions(skills)) == 1
    assert detect_collisions(skills, strict=True) == []


def test_strict_mode_higher_min_overlap(tmp_path) -> None:
    _write_skill(tmp_path, "one", 'Use when "foo bar" or "baz qux".')
    _write_skill(tmp_path, "two", 'Trigger: "foo bar", "baz qux".')
    skills = scan_skills([tmp_path])

    assert len(detect_collisions(skills)) == 1
    assert detect_collisions(skills, strict=True) == []


def test_emit_resolver_md_format(tmp_path) -> None:
    _write_skill(tmp_path, "one", 'Use when "foo bar" or "baz qux".')
    _write_skill(tmp_path, "two", 'Use when "foo bar" or "baz qux".')
    skills = scan_skills([tmp_path])
    collisions = detect_collisions(skills)
    output_path = emit_resolver_md(skills, collisions, tmp_path / "RESOLVER.md")

    output = output_path.read_text(encoding="utf-8")

    assert "### one" in output
    assert "### two" in output
    assert "## COLLISIONS" in output
    assert "one <-> two" in output


def test_emit_resolver_md_no_collisions(tmp_path) -> None:
    _write_skill(tmp_path, "one", 'Use when "alpha task".')
    _write_skill(tmp_path, "two", 'Use when "omega task".')
    skills = scan_skills([tmp_path])
    output_path = emit_resolver_md(skills, [], tmp_path / "RESOLVER.md")

    output = output_path.read_text(encoding="utf-8")

    assert "## COLLISIONS" in output
    assert "(none)" in output


def test_main_cli_exit_code(tmp_path) -> None:
    clean_root = tmp_path / "clean"
    _write_skill(clean_root, "one", 'Use when "alpha task".')
    _write_skill(clean_root, "two", 'Use when "omega task".')

    clean = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_resolvable",
            "--scan",
            str(clean_root),
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert clean.returncode == 0
    assert json.loads(clean.stdout)["collision_count"] == 0

    collision_root = tmp_path / "collision"
    _write_skill(collision_root, "one", 'Use when "foo bar" or "baz qux".')
    _write_skill(collision_root, "two", 'Trigger: "foo bar", "baz qux".')

    collision = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_resolvable",
            "--scan",
            str(collision_root),
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert collision.returncode == 1
    assert json.loads(collision.stdout)["collision_count"] == 1


def test_main_strict_flag(tmp_path) -> None:
    _write_skill(tmp_path, "one", 'Use when "foo bar" or "baz qux".')
    _write_skill(tmp_path, "two", 'Trigger: "foo bar", "baz qux".')

    default = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_resolvable",
            "--scan",
            str(tmp_path),
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    strict = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_resolvable",
            "--scan",
            str(tmp_path),
            "--strict",
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert default.returncode == 1
    assert json.loads(default.stdout)["collision_count"] == 1
    assert strict.returncode == 0
    assert json.loads(strict.stdout)["collision_count"] == 0
