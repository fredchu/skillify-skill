"""End-to-end smoke test for skillify itself.

Scaffolds a synthetic skill, runs audit on it, verifies expected verdict.
No mocking: exercises the full audit + scaffold + check_resolvable pipeline.
"""

from pathlib import Path

import pytest

from scripts.audit import audit_skill
from scripts.scaffold import scaffold


@pytest.mark.e2e
def test_scaffold_then_audit_returns_close_or_better(tmp_path: Path) -> None:
    skill_dir = scaffold(
        name="example_skill",
        target_dir=tmp_path,
        description='Example skill triggered by "example trigger" or "another trigger".',
    )
    skill_md = skill_dir / "SKILL.md"
    assert skill_md.exists()
    (skill_dir / "scripts" / "runner.py").write_text("VALUE = 1\n", encoding="utf-8")
    (skill_dir / "test" / "test_e2e_smoke.py").write_text(
        "def test_e2e_smoke() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    verdict_data = audit_skill(skill_md, project_root=skill_dir)

    assert verdict_data["verdict"] in {"properly skilled", "close"}
    assert verdict_data["items"]["skill_md_present"]["status"] == "pass"
    assert verdict_data["items"]["resolver_trigger"]["status"] == "pass"
