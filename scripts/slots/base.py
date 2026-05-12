"""Shared slot adapter contracts and score parsing helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


DIMENSIONS: tuple[str, ...] = (
    "goal",
    "depth",
    "specificity",
    "robustness",
    "trigger_clarity",
)


@dataclass
class SlotScore:
    slot: str
    model: str
    scores: dict[str, int]
    improvements: list[str]
    raw_response: str


class SlotAdapter(Protocol):
    """All adapters implement this protocol."""

    SLOT: str
    NAME: str

    @classmethod
    def is_available(cls) -> bool:
        """Return True iff the adapter can run without making network calls."""

    def score(self, skill_path: Path, task_description: str) -> SlotScore:
        """Score a skill file against a task description."""


class ScoreParseError(ValueError):
    """Raised when model output cannot be parsed into valid slot scores."""


def build_eval_prompt(skill_text: str, task_description: str) -> str:
    """Build the shared evaluator prompt used by all slot adapters."""

    dimensions = ", ".join(DIMENSIONS)
    return f"""Evaluate the skill content against the task description.

Score each dimension as an integer from 0 through 10:
- goal: goal achievement
- depth: depth
- specificity: specificity
- robustness: robustness
- trigger_clarity: trigger clarity

List the top 3-5 concrete improvements.

Output STRICT JSON only in this exact shape:
{{"scores": {{"goal": int, "depth": int, "specificity": int, "robustness": int, "trigger_clarity": int}}, "improvements": ["...", "..."]}}

Required score dimensions: {dimensions}

TASK DESCRIPTION:
{task_description}

SKILL CONTENT:
{skill_text}
"""


def parse_score_json(raw: str) -> tuple[dict[str, int], list[str]]:
    """Extract and validate score JSON from raw model output.

    Fenced JSON, bare JSON, and JSON embedded in surrounding markdown are
    accepted. Unknown dimensions are rejected to match the aggregator contract.
    """

    if not isinstance(raw, str) or not raw.strip():
        raise ScoreParseError("model output is empty")

    json_errors: list[str] = []
    validation_errors: list[str] = []
    for candidate in _json_candidates(raw):
        try:
            parsed = json.loads(candidate)
            return _validate_score_payload(parsed)
        except json.JSONDecodeError as exc:
            json_errors.append(str(exc))
        except ScoreParseError as exc:
            validation_errors.append(str(exc))

    if validation_errors:
        message = validation_errors[0]
    elif json_errors:
        message = json_errors[-1]
    else:
        message = "no JSON object found in model output"
    raise ScoreParseError(message)


def _json_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"```(?:json)?\s*(.*?)```", raw, re.IGNORECASE | re.DOTALL):
        candidates.append(match.group(1).strip())

    stripped = raw.strip()
    candidates.append(stripped)

    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            _, end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        candidates.append(raw[index : index + end])

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def _validate_score_payload(payload: Any) -> tuple[dict[str, int], list[str]]:
    if not isinstance(payload, dict):
        raise ScoreParseError("score payload must be a JSON object")

    scores = payload.get("scores")
    if not isinstance(scores, dict):
        raise ScoreParseError("score payload must include a scores object")

    expected = set(DIMENSIONS)
    score_keys = set(scores)
    missing = sorted(expected - score_keys)
    extra = sorted(score_keys - expected)
    if missing:
        raise ScoreParseError(f"missing score dimensions: {', '.join(missing)}")
    if extra:
        raise ScoreParseError(f"unknown score dimensions: {', '.join(extra)}")

    normalized_scores: dict[str, int] = {}
    for dimension in DIMENSIONS:
        score = scores[dimension]
        if not isinstance(score, int) or isinstance(score, bool):
            raise ScoreParseError(f"score for dimension '{dimension}' must be an integer")
        if not 0 <= score <= 10:
            raise ScoreParseError(
                f"score for dimension '{dimension}' must be in the inclusive range [0, 10]"
            )
        normalized_scores[dimension] = score

    improvements = payload.get("improvements")
    if not isinstance(improvements, list) or not all(
        isinstance(item, str) for item in improvements
    ):
        raise ScoreParseError("score payload must include improvements as a list of strings")

    return normalized_scores, improvements
