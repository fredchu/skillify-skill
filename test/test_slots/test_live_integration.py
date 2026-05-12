import os
from pathlib import Path

import pytest

from scripts.slots.slot_a_anthropic import AnthropicSlotA


@pytest.mark.live
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Live test requires ANTHROPIC_API_KEY to be set",
)
def test_slot_a_anthropic_live_score_returns_valid_slotscore():
    """Live API call to Anthropic. Skipped without ANTHROPIC_API_KEY.

    Verifies the adapter wires up correctly to a real model and returns a
    parseable SlotScore with all 5 dimensions in [0,10].
    """

    adapter = AnthropicSlotA()
    skill_path = Path("/Users/fredchu/.claude/skills/skillify/SKILL.md")
    score = adapter.score(skill_path, "Evaluate this meta-skill on its own design quality.")

    assert score.slot == "A"
    assert score.model.startswith("claude-")
    assert set(score.scores.keys()) == {
        "goal",
        "depth",
        "specificity",
        "robustness",
        "trigger_clarity",
    }
    for dim, val in score.scores.items():
        assert isinstance(val, int), f"{dim} score is not int"
        assert 0 <= val <= 10, f"{dim} score {val} out of [0,10]"
    assert isinstance(score.improvements, list)
