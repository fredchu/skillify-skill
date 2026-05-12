"""Deterministic aggregation for two-evaluator cross-modal scoring.

The aggregator is intentionally pure: it reads already-parsed evaluator
dictionaries, validates the documented score schema, and returns a verdict
without I/O, network calls, randomness, or time-dependent behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal


DIMENSIONS: tuple[str, ...] = (
    "goal",
    "depth",
    "specificity",
    "robustness",
    "trigger_clarity",
)

Verdict = Literal["pass", "fail", "split"]


def aggregate(
    evaluator_scores: list[dict[str, Any]],
    pass_mean: float = 7.0,
    floor: float = 5.0,
    split_gap: int = 3,
) -> dict[str, Any]:
    """Aggregate two evaluator score dictionaries into a cross-modal verdict.

    Args:
        evaluator_scores: Exactly two evaluator dictionaries. Each entry must
            include ``slot``, ``model``, and ``scores`` keys. ``scores`` must
            contain exactly the documented five dimensions with integer scores
            from 0 through 10.
        pass_mean: A dimension passes the mean gate when its mean is greater
            than or equal to this threshold. Equality passes.
        floor: A single evaluator score violates the floor only when it is
            strictly below this threshold. Equality is allowed.
        split_gap: A dimension is flagged as split only when max(score) -
            min(score) is strictly greater than this value. Equality is not a
            split.

    Returns:
        A dictionary containing per-dimension means, floor violations, split
        dimensions, and one of ``"pass"``, ``"fail"``, or ``"split"``.

    Raises:
        ValueError: If the evaluator list is not exactly two entries, required
        keys are missing, score dimensions do not match the contract, or any
        score is not an integer in the inclusive range [0, 10].

    Verdict precedence is fail > split > pass. This means a floor violation or
    failing mean returns ``"fail"`` even if the same input also has a split.
    """

    _validate_thresholds(pass_mean=pass_mean, floor=floor, split_gap=split_gap)
    normalized = _normalize_evaluators(evaluator_scores)

    means: dict[str, float] = {}
    floor_violations: list[dict[str, str | int]] = []
    split_dimensions: list[dict[str, str | int | list[int]]] = []
    mean_failures: list[str] = []

    for dimension in DIMENSIONS:
        scores = [evaluator["scores"][dimension] for evaluator in normalized]
        mean = sum(scores) / len(scores)
        means[dimension] = float(mean)

        if mean < pass_mean:
            mean_failures.append(dimension)

        for evaluator, score in zip(normalized, scores, strict=True):
            if score < floor:
                floor_violations.append(
                    {
                        "dimension": dimension,
                        "model": evaluator["model"],
                        "score": score,
                    }
                )

        gap = max(scores) - min(scores)
        if gap > split_gap:
            split_dimensions.append(
                {
                    "dimension": dimension,
                    "scores": scores,
                    "gap": gap,
                }
            )

    verdict: Verdict
    if mean_failures or floor_violations:
        verdict = "fail"
    elif split_dimensions:
        verdict = "split"
    else:
        verdict = "pass"

    return {
        "means": means,
        "floor_violations": floor_violations,
        "split_dimensions": split_dimensions,
        "verdict": verdict,
    }


def _validate_thresholds(*, pass_mean: float, floor: float, split_gap: int) -> None:
    if not isinstance(pass_mean, int | float):
        raise ValueError("pass_mean must be numeric")
    if not isinstance(floor, int | float):
        raise ValueError("floor must be numeric")
    if not isinstance(split_gap, int) or isinstance(split_gap, bool):
        raise ValueError("split_gap must be an integer")
    if not 0 <= pass_mean <= 10:
        raise ValueError("pass_mean must be in the inclusive range [0, 10]")
    if not 0 <= floor <= 10:
        raise ValueError("floor must be in the inclusive range [0, 10]")
    if split_gap < 0:
        raise ValueError("split_gap must be non-negative")


def _normalize_evaluators(
    evaluator_scores: list[dict[str, Any]],
) -> list[dict[str, str | dict[str, int]]]:
    if not isinstance(evaluator_scores, list):
        raise ValueError("evaluator_scores must be a list")
    if len(evaluator_scores) != 2:
        raise ValueError("evaluator_scores must contain exactly 2 evaluators")

    normalized: list[dict[str, str | dict[str, int]]] = []
    for index, evaluator in enumerate(evaluator_scores):
        if not isinstance(evaluator, Mapping):
            raise ValueError(f"evaluator at index {index} must be a mapping")

        slot = evaluator.get("slot")
        if slot not in {"A", "B"}:
            raise ValueError(f"evaluator at index {index} must have slot 'A' or 'B'")

        model = evaluator.get("model")
        if not isinstance(model, str) or not model:
            raise ValueError(f"evaluator at index {index} must have a non-empty model")

        scores = evaluator.get("scores")
        if not isinstance(scores, Mapping):
            raise ValueError(f"evaluator at index {index} must have scores mapping")

        score_keys = set(scores)
        expected_keys = set(DIMENSIONS)
        missing = sorted(expected_keys - score_keys)
        extra = sorted(score_keys - expected_keys)
        if missing:
            raise ValueError(
                f"evaluator at index {index} missing score dimensions: "
                f"{', '.join(missing)}"
            )
        if extra:
            raise ValueError(
                f"evaluator at index {index} has unknown score dimensions: "
                f"{', '.join(extra)}"
            )

        normalized_scores: dict[str, int] = {}
        for dimension in DIMENSIONS:
            score = scores[dimension]
            if not isinstance(score, int) or isinstance(score, bool):
                raise ValueError(
                    f"score for dimension '{dimension}' at evaluator index "
                    f"{index} must be an integer"
                )
            if not 0 <= score <= 10:
                raise ValueError(
                    f"score for dimension '{dimension}' at evaluator index "
                    f"{index} must be in the inclusive range [0, 10]"
                )
            normalized_scores[dimension] = score

        normalized.append(
            {
                "slot": slot,
                "model": model,
                "scores": normalized_scores,
            }
        )

    return normalized
