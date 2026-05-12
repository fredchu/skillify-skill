"""Cross-modal skill evaluation orchestrator.

This module composes Slot A with the first available Slot B adapter, scores a
``SKILL.md`` file, aggregates the two evaluator results, and writes a
content-bound receipt. Version 1 intentionally does not auto-apply fixes:
improvement application requires LLM agency and repository write judgment that
this deterministic script does not have. Failed or split cycle-1 results are
therefore returned as-is with a receipt for auditability.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from .aggregator import aggregate
from .receipt import write_receipt
from .slots import (
    ClaudeCodeSlotA,
    CodexDispatchSlotB,
    GeminiSlotB,
    OpenAISlotB,
    RawCodexSlotB,
    SlotAdapter,
    SlotScore,
)


SlotClass = type[SlotAdapter]
SLOT_B_FALLBACKS: tuple[SlotClass, ...] = (
    CodexDispatchSlotB,
    OpenAISlotB,
    GeminiSlotB,
    RawCodexSlotB,
)


def detect_available_slots() -> tuple[SlotClass | None, SlotClass | None]:
    """Return ``(slot_a_class, slot_b_class)`` for available adapters.

    Slot B is auto-detected in fallback order:
    ``codex_dispatch -> openai -> gemini -> raw_codex``. If Slot A is not
    available, both positions return ``None`` because the cross-modal contract
    cannot run. If Slot A is available but no Slot B is available, the second
    position returns ``None``.
    """

    if not ClaudeCodeSlotA.is_available():
        return None, None

    for slot_b_class in SLOT_B_FALLBACKS:
        if slot_b_class.is_available():
            return ClaudeCodeSlotA, slot_b_class

    return ClaudeCodeSlotA, None


def run_cycle(
    skill_path: Path,
    task_description: str,
    slot_a: SlotAdapter,
    slot_b: SlotAdapter,
    pass_mean: float = 7.0,
    floor: float = 5.0,
    split_gap: int = 3,
) -> dict[str, Any]:
    """Score ``skill_path`` with both slots and return evaluators + verdict."""

    evaluators = [
        _score_to_dict(slot_a.score(skill_path, task_description)),
        _score_to_dict(slot_b.score(skill_path, task_description)),
    ]
    aggregate_result = aggregate(
        evaluators,
        pass_mean=pass_mean,
        floor=floor,
        split_gap=split_gap,
    )
    return {
        "evaluators": evaluators,
        "aggregate": aggregate_result,
        "verdict": aggregate_result["verdict"],
    }


def evaluate(
    skill_path: Path,
    task_description: str,
    cycles: int = 2,
    base_dir: Path | None = None,
    skill_slug: str | None = None,
) -> dict[str, Any]:
    """Run cross-modal evaluation and write a content-bound receipt.

    The loop runs at most one scoring pass in v1 unless the first pass succeeds:
    there is no automatic fix application between cycles, so re-running a
    failed deterministic evaluation would only burn model calls. The ``cycles``
    argument remains part of the API to match the upstream contract and leave a
    stable extension point for a future agent-driven repair loop.

    If either required slot is unavailable, a summary with
    ``final_verdict == "unavailable"`` is returned and no receipt is written.
    """

    skill_path = Path(skill_path)
    slot_a_class, slot_b_class = detect_available_slots()
    if slot_a_class is None:
        return {
            "final_verdict": "unavailable",
            "reason": "Slot A unavailable: install Claude Code (`claude` CLI on PATH). Slot A uses your Claude Code subscription, not the Anthropic API.",
        }
    if slot_b_class is None:
        return {
            "final_verdict": "unavailable",
            "reason": "Slot B unavailable: install codex-dispatch/codex or configure OpenAI/Gemini.",
        }

    slot_a = slot_a_class()
    slot_b = slot_b_class()
    cycle_results: list[dict[str, Any]] = []
    max_cycles = max(1, cycles)

    for cycle_number in range(1, max_cycles + 1):
        cycle_result = run_cycle(skill_path, task_description, slot_a, slot_b)
        cycle_result["cycle"] = cycle_number
        cycle_results.append(cycle_result)
        break

    final_cycle = cycle_results[-1]
    slug = skill_slug or _skill_slug(skill_path)
    eval_data = {
        "skill_path": str(skill_path),
        "task_description": task_description,
        "cycles_requested": cycles,
        "cycles": cycle_results,
        "final_verdict": final_cycle["verdict"],
        "evaluator_summary": _evaluator_summary(final_cycle["evaluators"]),
        "v1_note": "No auto-fix applied; failed cycle-1 results stop after receipt.",
    }
    receipt_path = write_receipt(slug, skill_path, eval_data, base_dir=base_dir)

    return {
        "final_verdict": final_cycle["verdict"],
        "cycles_run": len(cycle_results),
        "receipt_path": str(receipt_path),
        "evaluator_summary": eval_data["evaluator_summary"],
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Exit codes: ``0`` on pass, ``1`` on fail/split, and ``2`` when evaluator
    slots are unavailable.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_path", type=Path, nargs="?", help="Path to SKILL.md.")
    parser.add_argument(
        "--output",
        dest="output_path",
        type=Path,
        help="Backward-compatible alias for the SKILL.md path.",
    )
    parser.add_argument(
        "--task",
        help="Task description. Defaults to the SKILL.md frontmatter description.",
    )
    parser.add_argument("--cycles", type=int, default=2, help="Maximum eval cycles.")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout.")
    args = parser.parse_args(argv)

    skill_path = args.skill_path or args.output_path
    if skill_path is None:
        parser.error("skill_path is required")

    task_description = args.task or _frontmatter_description(skill_path)
    result = evaluate(
        skill_path,
        task_description=task_description,
        cycles=args.cycles,
    )

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        _print_human(result)

    verdict = result["final_verdict"]
    if verdict == "pass":
        return 0
    if verdict == "unavailable":
        return 2
    return 1


def _score_to_dict(score: SlotScore) -> dict[str, Any]:
    return asdict(score)


def _evaluator_summary(evaluators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "slot": evaluator["slot"],
            "model": evaluator["model"],
            "scores": evaluator["scores"],
            "improvements": evaluator["improvements"],
        }
        for evaluator in evaluators
    ]


def _skill_slug(skill_path: Path) -> str:
    frontmatter = _load_frontmatter(skill_path)
    if frontmatter:
        name = frontmatter.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return skill_path.parent.name or skill_path.stem


def _frontmatter_description(skill_path: Path) -> str:
    frontmatter = _load_frontmatter(skill_path)
    if frontmatter:
        description = frontmatter.get("description")
        if isinstance(description, str) and description.strip():
            return description.strip()
    return "Evaluate this skill against its documented purpose."


def _load_frontmatter(skill_path: Path) -> dict[str, Any] | None:
    try:
        text = skill_path.read_text(encoding="utf-8")
    except OSError:
        return None

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


def _print_human(result: dict[str, Any]) -> None:
    print(f"verdict: {result['final_verdict']}")
    if "cycles_run" in result:
        print(f"cycles_run: {result['cycles_run']}")
    if "receipt_path" in result:
        print(f"receipt_path: {result['receipt_path']}")
    if "reason" in result:
        print(f"reason: {result['reason']}")


if __name__ == "__main__":
    raise SystemExit(main())
