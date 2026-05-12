from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts import skillify_it


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_skillify_it_basic_no_audit(tmp_path: Path) -> None:
    result = skillify_it.skillify_it("verb-demo", tmp_path)
    scaffolded = tmp_path / "verb-demo"

    assert result == {"scaffolded_path": str(scaffolded)}
    assert (scaffolded / "SKILL.md").exists()
    assert "audit" not in result


def test_skillify_it_with_audit(tmp_path: Path) -> None:
    result = skillify_it.skillify_it("verb-demo", tmp_path, run_audit=True)

    assert "audit" in result
    assert isinstance(result["audit"], dict)
    assert "verdict" in result["audit"]


def test_skillify_it_description_passed_to_scaffold(tmp_path: Path) -> None:
    description = 'Use when the user says "remember this as a skill".'

    result = skillify_it.skillify_it(
        "verb-demo",
        tmp_path,
        description=description,
    )
    text = (Path(result["scaffolded_path"]) / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])

    assert frontmatter["description"] == description


def test_skillify_it_existing_dir_raises_file_exists_error(tmp_path: Path) -> None:
    skillify_it.skillify_it("verb-demo", tmp_path)

    with pytest.raises(FileExistsError):
        skillify_it.skillify_it("verb-demo", tmp_path)


def test_main_cli_json_output(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.skillify_it",
            "cli-demo",
            "--target-dir",
            str(tmp_path),
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["scaffolded_path"] == str(tmp_path / "cli-demo")


def test_main_cli_audit_flag(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.skillify_it",
            "cli-demo",
            "--target-dir",
            str(tmp_path),
            "--audit",
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "audit" in payload
    assert "verdict" in payload["audit"]


def test_main_cli_existing_returns_nonzero(tmp_path: Path) -> None:
    skillify_it.skillify_it("cli-demo", tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.skillify_it",
            "cli-demo",
            "--target-dir",
            str(tmp_path),
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "error" in json.loads(result.stdout)


def test_main_cli_default_target_dir_is_home_dev() -> None:
    parser = skillify_it._build_parser()

    args = parser.parse_args(["default-demo"])

    assert args.target_dir == Path.home() / "dev"
