from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts import scaffold as scaffold_module


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scaffold_creates_dir_with_files(tmp_path: Path) -> None:
    created = scaffold_module.scaffold("my-skill", tmp_path)

    assert (created / "SKILL.md").exists()
    assert (created / "scripts" / "__init__.py").exists()
    assert (created / "test" / "test_smoke.py").exists()


def test_scaffold_skill_md_has_frontmatter(tmp_path: Path) -> None:
    created = scaffold_module.scaffold(
        "my-skill",
        tmp_path,
        description='Use when "my skill" is requested.',
    )
    text = (created / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])

    assert frontmatter["name"] == "my-skill"
    assert frontmatter["description"] == 'Use when "my skill" is requested.'


def test_scaffold_skill_md_has_phases(tmp_path: Path) -> None:
    created = scaffold_module.scaffold("my-skill", tmp_path)
    text = (created / "SKILL.md").read_text(encoding="utf-8")

    for phase in range(8):
        assert f"## Phase {phase}:" in text


def test_scaffold_existing_dir_raises(tmp_path: Path) -> None:
    scaffold_module.scaffold("my-skill", tmp_path)

    with pytest.raises(FileExistsError):
        scaffold_module.scaffold("my-skill", tmp_path)


def test_scaffold_overwrite_works(tmp_path: Path) -> None:
    created = scaffold_module.scaffold("my-skill", tmp_path)
    marker = created / "marker.txt"
    marker.write_text("old", encoding="utf-8")

    recreated = scaffold_module.scaffold("my-skill", tmp_path, overwrite=True)

    assert recreated == created
    assert not marker.exists()
    assert (recreated / "SKILL.md").exists()


def test_scaffold_smoke_test_passes(tmp_path: Path) -> None:
    created = scaffold_module.scaffold("my-skill", tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "test/test_smoke.py", "-q"],
        cwd=created,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_main_cli_basic(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.scaffold",
            "cli-skill",
            str(tmp_path),
            "--description",
            'Use when "cli skill" is requested.',
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "cli-skill" / "SKILL.md").exists()
