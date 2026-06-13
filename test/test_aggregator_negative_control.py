"""Negative-control regression tests for score discrimination (BACKLOG K2).

K2 asks: when Slot A and Slot B consistently agree closely (e.g. 9/9/9/8/9),
is that legitimate convergence or a prompt that constrains both models to a
narrow range (low discrimination)? Without feeding deliberately-bad scores and
asserting the aggregator does NOT rubber-stamp them, we can't tell.

These tests pin the aggregator's discrimination at the deterministic layer:
garbage scores MUST produce verdict="fail", and an asymmetric great/garbage
pair MUST fail on the floor rather than pass on the mean. They are instant,
need no LLM calls, and belong in CI regardless of the (more expensive)
prompt-discrimination test that runs a real bad-skill fixture through
cross_modal_eval.

Mirrors the helper style in test_aggregator.py.
"""

from __future__ import annotations

from scripts.aggregator import DIMENSIONS, aggregate


def _scores(default: int, **overrides: int) -> dict[str, int]:
    scores = {dimension: default for dimension in DIMENSIONS}
    scores.update(overrides)
    return scores


def _pair(a_scores: dict[str, int], b_scores: dict[str, int]) -> list[dict]:
    return [
        {"slot": "A", "model": "opus", "scores": a_scores},
        {"slot": "B", "model": "gpt-5", "scores": b_scores},
    ]


def test_negative_control_all_garbage_fails() -> None:
    """A deliberately-bad skill scored 2-3 across both providers must fail,
    with every dimension mean below the pass threshold and every score on the
    floor. If this ever passes, the aggregator has lost discrimination."""
    result = aggregate(_pair(_scores(2), _scores(3)))

    assert result["verdict"] == "fail"
    assert all(mean < 7.0 for mean in result["means"].values())
    # every dimension across both evaluators is below the floor (< 5)
    assert len(result["floor_violations"]) == 2 * len(DIMENSIONS)


def test_negative_control_one_great_one_garbage_fails() -> None:
    """One model loves it (10s), the other pans it (2s). This must FAIL on the
    floor, not pass on the averaged mean (which would be 6.0 here anyway).
    Guards against a high score laundering a garbage score via the mean."""
    result = aggregate(_pair(_scores(10), _scores(2)))

    assert result["verdict"] == "fail"
    assert result["floor_violations"]  # non-empty: the 2s trip the floor


def test_negative_control_single_catastrophic_dimension_fails() -> None:
    """An otherwise-perfect skill (all 10s) where ONE model flags ONE dimension
    as catastrophic (0) must fail. The mean alone would be 5.0 on that dim, but
    the floor is the real guard: one model's hard veto on one dimension is
    enough to sink it. Confirms a stellar average can't launder a single
    fatal flaw."""
    result = aggregate(_pair(_scores(10), _scores(10, goal=0)))

    assert result["verdict"] == "fail"
    assert any(v["dimension"] == "goal" and v["score"] == 0
               for v in result["floor_violations"])
