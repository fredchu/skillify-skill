"""Audit a skill against the skillify 11-item checklist."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

try:
    from scripts import check_resolvable, cross_modal_eval, receipt
except ImportError:
    import sys

    sys.modules.pop("scripts", None)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts import check_resolvable, cross_modal_eval, receipt


BLOCKING_ITEMS = (
    "skill_md_present",
    "code_present",
    "cross_modal_eval",
    "unit_tests",
    "resolver_trigger",
    "check_resolvable",
    "e2e_test",
)


def audit_skill(skill_path: Path, project_root: Path | None = None) -> dict[str, Any]:
    """Return a skillify audit verdict dictionary.

    Cross-modal evaluation blocks only when evaluator slots are available. In
    environments with no Slot A adapter, the item is marked N/A and omitted
    from the blocking score denominator.
    """

    skill_path = Path(skill_path)
    text = _read_text(skill_path)
    frontmatter = _load_frontmatter(skill_path)
    root = Path(project_root) if project_root is not None else _infer_project_root(skill_path)
    slug = _skill_slug(skill_path, frontmatter)
    test_files = _test_files(root)

    items: dict[str, dict[str, str]] = {}
    items["skill_md_present"] = _item(
        "pass" if frontmatter and isinstance(frontmatter.get("name"), str) else "fail",
        "SKILL.md has parseable YAML frontmatter with name."
        if frontmatter and isinstance(frontmatter.get("name"), str)
        else "SKILL.md missing or frontmatter lacks name.",
    )
    items["code_present"] = _code_present(root, text)

    items["cross_modal_eval"] = _cross_modal_eval(slug, skill_path)
    cross_modal_status = (
        "unavailable"
        if items["cross_modal_eval"]["status"] == "na"
        else _cross_modal_status(slug, skill_path)
    )

    items["unit_tests"] = _item(
        "pass" if test_files else "fail",
        f"Found {len(test_files)} test file(s)." if test_files else "No test/test_*.py files found.",
    )
    items["integration_tests"] = _integration_tests(test_files)
    items["llm_evals"] = _llm_evals(test_files)
    items["resolver_trigger"] = _resolver_trigger(frontmatter)
    items["resolver_eval"] = _resolver_eval(test_files)
    items["check_resolvable"] = _check_resolvable(root)
    items["e2e_test"] = _e2e_test(test_files)
    items["brain_filing"] = _brain_filing(root, text)

    applicable_blocking = [
        name for name in BLOCKING_ITEMS if items[name]["status"] != "na"
    ]
    blocking_failures = [
        name for name in applicable_blocking if items[name]["status"] == "fail"
    ]
    passed_blocking = len(applicable_blocking) - len(blocking_failures)
    if not blocking_failures:
        verdict = "properly skilled"
    elif passed_blocking >= 5:
        verdict = "close"
    else:
        verdict = "needs skillify"

    return {
        "skill_path": str(skill_path),
        "skill_slug": slug,
        "items": items,
        "verdict": verdict,
        "score": f"{passed_blocking}/{len(applicable_blocking)}",
        "cross_modal_status": cross_modal_status,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for skill audit."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_path", type=Path)
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Override project root. Defaults to the SKILL.md directory when it contains skill files.",
    )
    args = parser.parse_args(argv)

    result = audit_skill(args.skill_path, project_root=args.project_root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human(result)
    return 1 if result["verdict"] == "needs skillify" else 0


def _item(status: str, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_frontmatter(path: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            try:
                loaded = yaml.safe_load("\n".join(lines[1:index]))
            except yaml.YAMLError:
                return None
            return loaded if isinstance(loaded, dict) else None
    return None


def _infer_project_root(skill_path: Path) -> Path:
    parent = skill_path.parent
    if (parent / "scripts").exists() or (parent / "test").exists():
        return parent
    grandparent = parent.parent
    if (grandparent / "scripts").exists() or (grandparent / "test").exists():
        return grandparent
    return parent


def _skill_slug(skill_path: Path, frontmatter: dict[str, Any] | None) -> str:
    if frontmatter:
        name = frontmatter.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return skill_path.parent.name or skill_path.stem


def _test_files(project_root: Path) -> list[Path]:
    test_dir = project_root / "test"
    if not test_dir.exists():
        return []
    paths = {
        path
        for pattern in ("test_*.py", "*_e2e.py")
        for path in test_dir.rglob(pattern)
        if path.is_file()
    }
    return sorted(paths)


_CODE_EXTENSIONS = (
    ".py", ".sh", ".bash", ".zsh", ".fish",
    ".js", ".ts", ".mjs", ".cjs",
    ".rb", ".go", ".rs", ".lua", ".pl",
    ".swift", ".kt", ".java",
    ".applescript",
)
_CODE_IGNORE_NAMES = {"__init__.py", "README.md", "README"}


def _code_present(project_root: Path, skill_text: str) -> dict[str, str]:
    scripts_dir = project_root / "scripts"
    code_files: list[Path] = []
    if scripts_dir.exists():
        for path in scripts_dir.iterdir():
            if not path.is_file():
                continue
            if path.name in _CODE_IGNORE_NAMES:
                continue
            if path.suffix.lower() in _CODE_EXTENSIONS:
                code_files.append(path)
            elif path.stat().st_mode & 0o111:
                # Executable file with no recognized extension (e.g. `mytool`).
                code_files.append(path)
    if code_files:
        extensions = sorted({p.suffix.lower() or "(no-ext)" for p in code_files})
        return _item(
            "pass",
            f"Found {len(code_files)} script file(s) ({', '.join(extensions)}).",
        )
    if re.search(r"\bpure[- ]prose\b|\bno code\b", skill_text, re.IGNORECASE):
        return _item("na", "Skill declares itself pure-prose.")
    return _item(
        "fail",
        f"No code files found under scripts/. Checked extensions: {', '.join(_CODE_EXTENSIONS)} plus executables.",
    )


def _cross_modal_eval(skill_slug: str, skill_path: Path) -> dict[str, str]:
    slot_a_class, slot_b_class = cross_modal_eval.detect_available_slots()
    if slot_a_class is None and slot_b_class is None:
        return _item(
            "na",
            "Cross-modal eval unavailable: no local evaluator slots detected.",
        )

    receipt_status = _cross_modal_status(skill_slug, skill_path)
    if receipt_status == "found":
        return _item("pass", "Current cross-modal receipt found.")
    return _item(
        "fail",
        f"Cross-modal evaluator slots detected but receipt status is {receipt_status}.",
    )


def _cross_modal_status(skill_slug: str, skill_path: Path) -> str:
    if not skill_path.exists():
        return "missing"
    current = receipt.find_current_receipt(skill_slug, skill_path)
    if current is not None:
        return "found"
    if receipt.list_receipts(skill_slug):
        return "stale"
    return "missing"


def _integration_tests(test_files: list[Path]) -> dict[str, str]:
    for test_file in test_files:
        text = _read_text(test_file)
        if "integration" in test_file.name.lower() or "@pytest.mark.integration" in text:
            return _item("pass", f"Integration coverage found in {test_file.name}.")
    return _item("na", "No integration tests detected.")


def _llm_evals(test_files: list[Path]) -> dict[str, str]:
    for test_file in test_files:
        text = _read_text(test_file)
        if "eval" in test_file.name.lower() or re.search(r"assert.*evaluator", text, re.DOTALL):
            return _item("pass", f"LLM/evaluator coverage found in {test_file.name}.")
    return _item("na", "No LLM eval tests detected.")


def _resolver_trigger(frontmatter: dict[str, Any] | None) -> dict[str, str]:
    description = ""
    if frontmatter and isinstance(frontmatter.get("description"), str):
        description = frontmatter["description"]
    quoted = re.findall(r'"([^"\n]+)"|`([^`\n]+)`', description)
    quoted_count = sum(1 for left, right in quoted if (left or right).strip())
    keyword_count = len(
        re.findall(
            r"\b(use when|user says|trigger|trigger phrase|invoked when)\b",
            description,
            re.IGNORECASE,
        )
    )
    signal_count = quoted_count + keyword_count
    if signal_count >= 2:
        return _item("pass", f"Found {signal_count} resolver trigger signal(s).")
    return _item("fail", "Description needs at least two trigger phrases/signals.")


def _resolver_eval(test_files: list[Path]) -> dict[str, str]:
    for test_file in test_files:
        if "check_resolvable" in _read_text(test_file):
            return _item("pass", f"Resolver eval found in {test_file.name}.")
    return _item("na", "No resolver-routing test detected.")


def _check_resolvable(project_root: Path) -> dict[str, str]:
    local = project_root / "scripts" / "check_resolvable.py"
    if local.exists():
        return _item("pass", f"Found {local}.")

    bundled = Path(__file__).with_name("check_resolvable.py")
    if bundled.exists():
        return _item("pass", f"Bundled checker available at {bundled}.")

    return _item("fail", "scripts/check_resolvable.py not found.")


def _e2e_test(test_files: list[Path]) -> dict[str, str]:
    for test_file in test_files:
        text = _read_text(test_file)
        if (
            test_file.match("test_e2e*.py")
            or test_file.match("*_e2e.py")
            or "@pytest.mark.e2e" in text
        ):
            return _item("pass", f"E2E coverage found in {test_file.name}.")
    return _item("fail", "No E2E smoke test detected.")


def _brain_filing(project_root: Path, skill_text: str) -> dict[str, str]:
    scripts_dir = project_root / "scripts"
    if not scripts_dir.exists():
        return _item("na", "No scripts directory to inspect for persistent writes.")

    write_pattern = re.compile(
        r"Path\.write_text|\.write_text\(|json\.dump|git commit|subprocess\..*git",
        re.DOTALL,
    )
    writes = [
        path.name
        for path in scripts_dir.glob("*.py")
        if path.is_file() and write_pattern.search(_read_text(path))
    ]
    if not writes:
        return _item("na", "No persistent writes detected in scripts/*.py.")

    if re.search(r"(^|\n)##?\s*(Output|Persists to)\b|Output:", skill_text, re.IGNORECASE):
        return _item("pass", f"Persistent writes declared; detected in {', '.join(writes)}.")
    return _item("fail", f"Persistent writes detected but no Output declaration: {', '.join(writes)}.")


def _print_human(result: dict[str, Any]) -> None:
    print(f"verdict: {result['verdict']}")
    print(f"score: {result['score']}")
    print(f"cross_modal: {result['cross_modal_status']}")
    for name, item in result["items"].items():
        print(f"- {name}: {item['status']} - {item['detail']}")


if __name__ == "__main__":
    raise SystemExit(main())
