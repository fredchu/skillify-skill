from __future__ import annotations

import pytest

from scripts.aggregator import DIMENSIONS, aggregate


def _scores(default: int, **overrides: int) -> dict[str, int]:
    scores = {dimension: default for dimension in DIMENSIONS}
    scores.update(overrides)
    return scores


def _evaluator(slot: str, model: str, scores: dict[str, int]) -> dict:
    return {
        "slot": slot,
        "model": model,
        "scores": scores,
    }


def _pair(
    a_scores: dict[str, int],
    b_scores: dict[str, int],
) -> list[dict]:
    return [
        _evaluator("A", "opus", a_scores),
        _evaluator("B", "gpt-5", b_scores),
    ]


def test_pass_clean() -> None:
    result = aggregate(_pair(_scores(8), _scores(8)))

    assert result["verdict"] == "pass"
    assert result["means"] == {dimension: 8.0 for dimension in DIMENSIONS}
    assert result["floor_violations"] == []
    assert result["split_dimensions"] == []


def test_fail_on_mean() -> None:
    result = aggregate(_pair(_scores(6), _scores(6)))

    assert result["verdict"] == "fail"
    assert result["means"] == {dimension: 6.0 for dimension in DIMENSIONS}
    assert result["floor_violations"] == []
    assert result["split_dimensions"] == []


def test_fail_on_floor() -> None:
    result = aggregate(_pair(_scores(10), _scores(10, depth=4)))

    assert result["verdict"] == "fail"
    assert result["means"]["depth"] == 7.0
    assert result["floor_violations"] == [
        {
            "dimension": "depth",
            "model": "gpt-5",
            "score": 4,
        }
    ]
    assert result["split_dimensions"] == [{"dimension": "depth", "scores": [10, 4], "gap": 6}]


def test_split_only() -> None:
    result = aggregate(_pair(_scores(9), _scores(9, specificity=5)))

    assert result["verdict"] == "split"
    assert result["means"]["specificity"] == 7.0
    assert result["floor_violations"] == []
    assert result["split_dimensions"] == [
        {
            "dimension": "specificity",
            "scores": [9, 5],
            "gap": 4,
        }
    ]


def test_floor_at_threshold() -> None:
    result = aggregate(_pair(_scores(9), _scores(9, robustness=5)))

    assert result["verdict"] == "split"
    assert result["floor_violations"] == []
    assert result["means"]["robustness"] == 7.0


def test_split_at_threshold() -> None:
    result = aggregate(_pair(_scores(9), _scores(9, trigger_clarity=6)))

    assert result["verdict"] == "pass"
    assert result["means"]["trigger_clarity"] == 7.5
    assert result["split_dimensions"] == []


def test_mean_at_threshold() -> None:
    result = aggregate(_pair(_scores(8), _scores(8, goal=6)))

    assert result["verdict"] == "pass"
    assert result["means"]["goal"] == 7.0
    assert result["floor_violations"] == []
    assert result["split_dimensions"] == []


@pytest.mark.parametrize(
    ("bad_scores", "expected_message"),
    [
        (
            [{"slot": "A", "model": "opus", "scores": _scores(8)}],
            "exactly 2 evaluators",
        ),
        (
            _pair(
                {dimension: 8 for dimension in DIMENSIONS if dimension != "goal"},
                _scores(8),
            ),
            "missing score dimensions: goal",
        ),
        (
            _pair(_scores(8, depth=11), _scores(8)),
            "inclusive range",
        ),
        (
            _pair(_scores(8, depth=True), _scores(8)),
            "must be an integer",
        ),
        (
            _pair({**_scores(8), "fluency": 8}, _scores(8)),
            "unknown score dimensions: fluency",
        ),
    ],
)
def test_invalid_scores_raises(
    bad_scores: list[dict],
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        aggregate(bad_scores)


def test_precedence_fail_over_split() -> None:
    result = aggregate(_pair(_scores(10), _scores(10, specificity=4)))

    assert result["verdict"] == "fail"
    assert result["means"]["specificity"] == 7.0
    assert result["floor_violations"] == [
        {
            "dimension": "specificity",
            "model": "gpt-5",
            "score": 4,
        }
    ]
    assert result["split_dimensions"] == [
        {
            "dimension": "specificity",
            "scores": [10, 4],
            "gap": 6,
        }
    ]
