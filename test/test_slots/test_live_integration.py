import shutil
from pathlib import Path

import pytest

from scripts.slots.slot_a_claude_code import ClaudeCodeSlotA


@pytest.mark.live
@pytest.mark.skipif(
    not shutil.which("claude"),
    reason="Live test requires `claude` CLI in PATH",
)
def test_slot_a_claude_code_live_score():
    """Live Claude Code CLI call. Skipped when `claude` is not on PATH.

    Verifies the adapter wires up correctly to a real model and returns a
    parseable SlotScore with all 5 dimensions in [0,10].
    """

    adapter = ClaudeCodeSlotA()
    skill_path = Path("/Users/fredchu/.claude/skills/skillify/SKILL.md")
    score = adapter.score(skill_path, "Evaluate this meta-skill on its own design quality.")

    assert score.slot == "A"
    assert score.model == "claude-code-cli"
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
