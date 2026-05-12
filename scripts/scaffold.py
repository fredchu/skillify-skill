"""Generate a new skill skeleton."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


def scaffold(
    name: str,
    target_dir: Path,
    description: str = "TODO: write description with trigger phrases.",
    overwrite: bool = False,
) -> Path:
    """Create ``target_dir/{name}/`` with a starter skill tree."""

    slug = _slugify(name)
    skill_dir = Path(target_dir) / slug
    if skill_dir.exists():
        if not overwrite:
            raise FileExistsError(f"{skill_dir} already exists")
        shutil.rmtree(skill_dir)

    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "test").mkdir()
    display_name = _display_name(name)

    (skill_dir / "SKILL.md").write_text(
        _skill_md(slug, display_name, description),
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "__init__.py").write_text(
        '"""Script helpers for this skill."""\n',
        encoding="utf-8",
    )
    (skill_dir / "test" / "__init__.py").write_text("", encoding="utf-8")
    (skill_dir / "test" / "test_smoke.py").write_text(
        """from __future__ import annotations


def test_smoke() -> None:
    assert True
""",
        encoding="utf-8",
    )
    (skill_dir / ".gitignore").write_text(
        """__pycache__/
.pytest_cache/
*.pyc
.DS_Store
""",
        encoding="utf-8",
    )
    return skill_dir


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for scaffolding."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("target_dir", type=Path)
    parser.add_argument(
        "--description",
        default="TODO: write description with trigger phrases.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing skill dir.")
    args = parser.parse_args(argv)

    try:
        created = scaffold(
            args.name,
            args.target_dir,
            description=args.description,
            overwrite=args.force,
        )
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(created)
    return 0


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return slug or "new-skill"


def _display_name(name: str) -> str:
    words = re.split(r"[\s_-]+", name.strip())
    return " ".join(word[:1].upper() + word[1:] for word in words if word) or "New Skill"


def _skill_md(slug: str, display_name: str, description: str) -> str:
    return f"""---
name: {slug}
description: |-
  {description}
---

# {display_name}

## Triggers

- TODO: Add real user phrases, for example "use {slug}" and "run {slug}".

## Phase 0: Should this be a skill?

TODO: Define why this behavior will be reused and why it needs a skill.

## Phase 1: Audit

TODO: List current assets, missing checklist items, and constraints.

## Phase 2: Write SKILL.md + Code

TODO: Describe deterministic scripts and the user-facing skill contract.

## Phase 3: Cross-Modal Eval

TODO: Choose the representative task and record receipt status.

## Phase 4: Tests

TODO: Add unit tests, integration tests when applicable, and LLM evals when needed.

## Phase 5: Resolver Trigger

TODO: Verify trigger phrases are concrete and resolvable.

## Phase 6: E2E + Persistent-location Filing

TODO: Add end-to-end smoke coverage and declare persistent writes.

## Phase 7: Verify

TODO: Run tests and audit before shipping.

## Output Format

TODO: Describe files, JSON, text, or other outputs this skill creates.
"""


if __name__ == "__main__":
    raise SystemExit(main())
