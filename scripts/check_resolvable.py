"""Scan installed skills for resolver trigger ambiguity.

This module reads ``SKILL.md`` frontmatter, extracts resolver-style triggers
from the ``description`` field, and flags pairs of skills whose triggers
overlap enough to make routing ambiguous. The trigger extractor is heuristic:
it collects double-quoted phrases, backtick-quoted slash commands, and phrases
following markers such as ``when user says X``, ``trigger: X``, and
``use when X``. When no marker is found, the full lowercased description is
kept as a single blob and blob-to-blob collision checks compare shared word
tokens of length four or greater. Use ``--strict`` to de-duplicate identical
skills by content hash, require stronger explicit-trigger overlap, and skip
blob-to-blob comparisons.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml


EXCLUDED_DIRS = {".codex-dispatch", ".pytest_cache", "__pycache__"}
FRONTMATTER_BOUNDARY = "---"
STOP_TRIGGER_FRAGMENTS = {"and", "or"}

_DOUBLE_QUOTED_RE = re.compile(r'"([^"\n]+)"')
_SLASH_COMMAND_RE = re.compile(r"`(/[^`]+)`")
_MARKER_RE = re.compile(
    r"(?:when\s+(?:the\s+)?user\s+says?|trigger\s*:|use\s+when)\s*:?\s*"
    r"(.+?)(?=(?:\.\s|\n\s*\n|$))",
    re.IGNORECASE | re.DOTALL,
)
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_/-]*")


def scan_skills(roots: list[Path]) -> list[dict[str, Any]]:
    """Find and parse ``SKILL.md`` files under ``roots``.

    Returns dictionaries with ``path``, ``name``, ``description``, and
    ``triggers`` keys. Malformed frontmatter, missing ``name`` values, and
    missing ``description`` values are skipped silently. Files under
    ``.codex-dispatch``, ``.pytest_cache``, or ``__pycache__`` are skipped.
    """

    skills: list[dict[str, Any]] = []
    skill_paths: list[tuple[int, Path]] = []
    for root_index, root in enumerate(roots):
        root = Path(root).expanduser()
        if not root.exists():
            continue

        for skill_path in sorted(root.rglob("SKILL.md")):
            if _is_excluded(skill_path):
                continue
            skill_paths.append((root_index, skill_path))

    # First-seen wins after deterministic root/path sorting. This keeps one copy
    # when the same skill is installed directly and cached by a plugin.
    seen_hashes: set[str] = set()
    seen_names: set[str] = set()
    for _, skill_path in sorted(skill_paths, key=lambda item: (item[0], str(item[1]))):
        content_hash = _content_sha256(skill_path)
        if content_hash is None or content_hash in seen_hashes:
            continue

        frontmatter = _load_frontmatter(skill_path)
        if frontmatter is None:
            continue

        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(description, str) or not description.strip():
            continue
        normalized_name = _normalize_trigger(name)
        if normalized_name in seen_names:
            continue
        seen_hashes.add(content_hash)
        seen_names.add(normalized_name)

        skills.append(
            {
                "path": skill_path,
                "name": name.strip(),
                "description": description.strip(),
                "triggers": _extract_triggers(description),
            }
        )

    return skills


def detect_collisions(
    skills: list[dict[str, Any]],
    min_overlap: int = 2,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Return skill pairs sharing at least ``min_overlap`` triggers.

    Exact trigger phrase comparison is case-insensitive and whitespace-stripped.
    When both skills fell back to full-description trigger blobs, collision
    comparison uses shared word tokens of length four or greater. Strict mode
    requires at least three exact explicit triggers, skips blob-vs-blob checks,
    and requires at least four shared word tokens for mixed explicit/blob pairs.
    """

    collisions: list[dict[str, Any]] = []
    for skill_a, skill_b in combinations(skills, 2):
        triggers_a = {_normalize_trigger(trigger) for trigger in skill_a["triggers"]}
        triggers_b = {_normalize_trigger(trigger) for trigger in skill_b["triggers"]}
        triggers_a.discard("")
        triggers_b.discard("")

        is_blob_a = _is_blob_skill(skill_a)
        is_blob_b = _is_blob_skill(skill_b)
        shared = sorted(triggers_a & triggers_b)
        threshold = min_overlap

        if strict:
            if is_blob_a and is_blob_b:
                continue
            if is_blob_a != is_blob_b:
                shared = sorted(_trigger_tokens(skill_a) & _trigger_tokens(skill_b))
                threshold = max(min_overlap, 4)
            else:
                threshold = max(min_overlap, 3)
        elif len(shared) < min_overlap and is_blob_a and is_blob_b:
            shared = sorted(_blob_tokens(skill_a) & _blob_tokens(skill_b))

        if len(shared) >= threshold:
            collisions.append(
                {
                    "skills": [skill_a["name"], skill_b["name"]],
                    "paths": [skill_a["path"], skill_b["path"]],
                    "shared_triggers": shared,
                    "overlap_count": len(shared),
                }
            )

    return collisions


def emit_resolver_md(
    skills: list[dict[str, Any]],
    collisions: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    """Write a static markdown registry of skills, triggers, and collisions."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Skill Resolver",
        "",
        "## Skills",
        "",
    ]
    for skill in sorted(skills, key=lambda item: item["name"].lower()):
        lines.extend(
            [
                f"### {skill['name']}",
                "",
                f"- Path: `{skill['path']}`",
                f"- Description: {skill['description']}",
                "- Triggers:",
            ]
        )
        for trigger in skill["triggers"]:
            lines.append(f"  - `{trigger}`")
        lines.append("")

    lines.extend(["## COLLISIONS", ""])
    if collisions:
        for collision in collisions:
            skill_names = " <-> ".join(collision["skills"])
            shared = ", ".join(f"`{trigger}`" for trigger in collision["shared_triggers"])
            lines.extend(
                [
                    f"### {skill_names}",
                    "",
                    f"- Overlap count: {collision['overlap_count']}",
                    f"- Shared triggers: {shared}",
                    f"- Paths: `{collision['paths'][0]}` and `{collision['paths'][1]}`",
                    "",
                ]
            )
    else:
        lines.append("(none)")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for scanning skills and optionally emitting RESOLVER.md."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scan",
        nargs="+",
        type=Path,
        default=None,
        metavar="PATH",
        help="Directories to scan for SKILL.md files.",
    )
    parser.add_argument(
        "--emit",
        type=Path,
        help="Optional path where a static RESOLVER.md should be written.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON report instead of human-readable text.",
    )
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=2,
        help="Minimum shared triggers required to flag a collision.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Reduce false positives by skipping blob-vs-blob checks and raising overlap thresholds.",
    )
    args = parser.parse_args(argv)

    roots = args.scan if args.scan is not None else _default_roots()
    skills = scan_skills(roots)
    collisions = detect_collisions(
        skills,
        min_overlap=args.min_overlap,
        strict=args.strict,
    )

    emitted_path: Path | None = None
    if args.emit is not None:
        emitted_path = emit_resolver_md(skills, collisions, args.emit)

    report = {
        "skill_count": len(skills),
        "collision_count": len(collisions),
        "skills": skills,
        "collisions": collisions,
        "resolver_path": emitted_path,
        "strict": args.strict,
    }

    if args.json:
        print(json.dumps(_jsonable(report), indent=2, sort_keys=True))
    else:
        _print_human_report(report)

    return 1 if collisions else 0


def _default_roots() -> list[Path]:
    claude_home = Path.home() / ".claude"
    return [claude_home / "skills", claude_home / "plugins" / "cache"]


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _content_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_frontmatter(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_BOUNDARY:
        return None

    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_BOUNDARY:
            end_index = index
            break
    if end_index is None:
        return None

    raw_frontmatter = "\n".join(lines[1:end_index])
    try:
        loaded = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError:
        return None

    if not isinstance(loaded, dict):
        return None
    return loaded


def _extract_triggers(description: str) -> list[str]:
    triggers: list[str] = []

    for phrase in _DOUBLE_QUOTED_RE.findall(description):
        _append_trigger(triggers, phrase)

    for command in _SLASH_COMMAND_RE.findall(description):
        _append_trigger(triggers, command)

    for marker_match in _MARKER_RE.findall(description):
        for phrase in _phrases_from_marker(marker_match):
            _append_trigger(triggers, phrase)

    if not triggers:
        _append_trigger(triggers, description)

    return triggers


def _phrases_from_marker(segment: str) -> list[str]:
    segment = re.sub(
        r"^\s*(?:the\s+)?user\s+says?\s*:?\s*",
        "",
        segment,
        flags=re.IGNORECASE,
    )
    quoted = _DOUBLE_QUOTED_RE.findall(segment)
    commands = _SLASH_COMMAND_RE.findall(segment)
    if quoted or commands:
        return [*quoted, *commands]

    parts = re.split(r"\s*(?:,|\bor\b|\band\b|;)\s*", segment)
    return [part for part in parts if part.strip()]


def _append_trigger(triggers: list[str], phrase: str) -> None:
    normalized = _normalize_trigger(phrase)
    if normalized in STOP_TRIGGER_FRAGMENTS:
        return
    if normalized and normalized not in triggers:
        triggers.append(normalized)


def _normalize_trigger(phrase: str) -> str:
    normalized = re.sub(r"\s+", " ", phrase).strip().lower()
    return normalized.strip(" \t\r\n'\".,;:!?")


def _is_blob_skill(skill: dict[str, Any]) -> bool:
    triggers = skill.get("triggers")
    description = skill.get("description")
    return (
        isinstance(triggers, list)
        and len(triggers) == 1
        and isinstance(description, str)
        and _normalize_trigger(description) == triggers[0]
    )


def _blob_tokens(skill: dict[str, Any]) -> set[str]:
    description = _normalize_trigger(skill["description"])
    return {token for token in _WORD_RE.findall(description) if len(token) >= 4}


def _trigger_tokens(skill: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for trigger in skill.get("triggers", []):
        if isinstance(trigger, str):
            tokens.update(token for token in _WORD_RE.findall(trigger) if len(token) >= 4)
    return tokens


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _print_human_report(report: dict[str, Any]) -> None:
    print(f"Skills scanned: {report['skill_count']}")
    print(f"Collisions found: {report['collision_count']}")
    if report["resolver_path"] is not None:
        print(f"Resolver written: {report['resolver_path']}")

    for collision in report["collisions"]:
        print("")
        print("Collision: " + " <-> ".join(collision["skills"]))
        print(f"Overlap count: {collision['overlap_count']}")
        print("Shared triggers: " + ", ".join(collision["shared_triggers"]))
        print(f"Paths: {collision['paths'][0]} | {collision['paths'][1]}")


if __name__ == "__main__":
    raise SystemExit(main())
