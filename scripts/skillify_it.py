"""Thin orchestration wrapper: scaffold + optional audit in one command.

This is the entry point invoked when a user says "skillify it" or similar
verb phrases (see SKILL.md "Skillify as a verb"). The script does not mine
the conversation; the calling LLM has already extracted the name, description,
and procedure. This wrapper just makes scaffold-then-audit feel like one step.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts import audit, scaffold
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts import audit, scaffold


def skillify_it(
    name: str,
    target_dir: Path,
    description: str | None = None,
    run_audit: bool = False,
) -> dict[str, Any]:
    """Scaffold a skill skeleton and optionally audit it immediately."""

    scaffolded = scaffold.scaffold(
        name=name,
        target_dir=target_dir,
        description=description
        or f"TODO: write description with trigger phrases for {name}.",
    )
    result: dict[str, Any] = {"scaffolded_path": str(scaffolded)}
    if run_audit:
        skill_md = scaffolded / "SKILL.md"
        result["audit"] = audit.audit_skill(skill_md, project_root=scaffolded)
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skillify_it",
        description="Skillify it: scaffold a skill skeleton and optionally audit.",
    )
    parser.add_argument("name", help="Skill name in kebab-case, e.g. webhook-oauth")
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path.home() / "dev",
        help="Parent directory for the new skill (default: ~/dev)",
    )
    parser.add_argument(
        "--description",
        help="One-paragraph description for SKILL.md frontmatter.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="After scaffolding, run audit_skill on the new skill and include verdict.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a human-readable summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = skillify_it(
            name=args.name,
            target_dir=args.target_dir,
            description=args.description,
            run_audit=args.audit,
        )
    except FileExistsError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}))
        else:
            print(f"Error: target already exists: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Scaffolded: {result['scaffolded_path']}")
        if "audit" in result:
            audit_result = result["audit"]
            print(
                f"Audit verdict: {audit_result['verdict']} "
                f"({audit_result.get('score', 'n/a')})"
            )
            print(
                "  cross_modal_status: "
                f"{audit_result.get('cross_modal_status', 'n/a')}"
            )
            for key, item in sorted(audit_result.get("items", {}).items()):
                icon = {"pass": "[pass]", "fail": "[fail]", "na": "[na]"}.get(
                    item.get("status"),
                    "[?]",
                )
                print(f"    {icon} {key}: {item.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
