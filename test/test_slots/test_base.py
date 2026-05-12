from __future__ import annotations

import pytest

from scripts.slots.base import DIMENSIONS, ScoreParseError, build_eval_prompt, parse_score_json


VALID_JSON = """{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": ["tighten triggers", "add examples"]}"""


def test_parse_fenced_json() -> None:
    scores, improvements = parse_score_json(f"```json\n{VALID_JSON}\n```")

    assert scores["goal"] == 8
    assert improvements == ["tighten triggers", "add examples"]


def test_parse_bare_json() -> None:
    scores, improvements = parse_score_json(VALID_JSON)

    assert scores == {
        "goal": 8,
        "depth": 7,
        "specificity": 9,
        "robustness": 6,
        "trigger_clarity": 10,
    }
    assert improvements == ["tighten triggers", "add examples"]


def test_parse_embedded_in_prose() -> None:
    raw = f"Here is the requested evaluation:\n\n{VALID_JSON}\n\nDone."

    scores, improvements = parse_score_json(raw)

    assert scores["specificity"] == 9
    assert improvements == ["tighten triggers", "add examples"]


def test_parse_missing_dimension_raises() -> None:
    raw = """{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6}, "improvements": []}"""

    with pytest.raises(ScoreParseError, match="missing score dimensions: trigger_clarity"):
        parse_score_json(raw)


def test_parse_score_out_of_range_raises() -> None:
    raw = """{"scores": {"goal": 15, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10}, "improvements": []}"""

    with pytest.raises(ScoreParseError, match="inclusive range"):
        parse_score_json(raw)


def test_parse_extra_dimension_raises() -> None:
    raw = """{"scores": {"goal": 8, "depth": 7, "specificity": 9, "robustness": 6, "trigger_clarity": 10, "style": 4}, "improvements": []}"""

    with pytest.raises(ScoreParseError, match="unknown score dimensions: style"):
        parse_score_json(raw)


def test_build_eval_prompt_includes_dimensions() -> None:
    prompt = build_eval_prompt("skill body", "task body")

    for dimension in DIMENSIONS:
        assert dimension in prompt
    assert "skill body" in prompt
    assert "task body" in prompt
