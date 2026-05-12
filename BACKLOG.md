# Skillify Backlog

Running backlog of known issues, deferred scope, and design questions for this fork. Items are organized by ship-blocking priority. Each item links back to the run / RED_TEAM finding / dogfood test that surfaced it.

This is intentionally public — a roadmap is a contribution to anyone evaluating whether to adopt this fork.

## Status legend

- 🚨 **Blocker** — must close before next public release
- 🔧 **Known issue** — open but not ship-blocking; visible to users
- 📋 **v2 scope** — explicitly deferred
- 💭 **Open design question** — needs decision (often via real-use signal)
- 🐛 **Dogfood candidate** — skill to try `python3 -m scripts.audit` against
- 🌱 **Article-derived** — surfaced by comparison with Garry Tan's original article or e2e dogfood

---

## 🚨 Blockers

Nothing currently blocking.

(B1 GitHub publish ✅ done — live at https://github.com/fredchu/skillify-skill)

---

## 🔧 Known issues

### K1 — Agent-tool LLM-driven path is aspirational prose only
`SKILL.md` Phase 3 and the verb-workflow section both describe an Agent-tool path "preferred when invoked from inside a Claude Code session." There is no helper script, no test, and no e2e verification that Claude actually follows the prose discipline.

**Source**: Run 2 RED_TEAM finding CF4 (deferred); same shape applies to verb workflow added in run 4.

**Estimate**: ½ day to design + 1-2 hours to add an e2e fixture that simulates an LLM following the protocol.

### K2 — No negative-control regression test for score convergence
Slot A (claude-code-cli) and Slot B (codex-dispatch/gpt-5) consistently agree closely (9/9/9/8/9 on skillify, identical scores across two runs). This could be legitimate convergence on a well-designed skill, or it could be a prompt that constrains both LLMs to a narrow range (low discrimination). Without a negative-control case — feeding a deliberately bad SKILL.md and verifying both slots score it low — we don't know.

**Source**: Run 2 RED_TEAM observation.

**Estimate**: 1-2 hours to write a deliberately-bad fixture skill and assert both slots return verdict=fail.

### K3 — Mocked slot tests verify shape, not semantics
The 37 mocked slot tests verify that when the underlying SDK/subprocess returns a well-formed response, our adapter parses it correctly. They don't catch a real LLM returning garbage in a malformed-but-superficially-JSON-shaped way.

**Source**: Run 1 RED_TEAM blind spot B4.

**Estimate**: 1-2 hours to add fuzz-style tests with malformed responses (truncated JSON, embedded prose with conflicting scores, etc.).

### K4 — No test for SKILL.md discoverability in real CC routing
`audit.py`'s `resolver_trigger` item only checks the description field has ≥2 trigger phrases; it doesn't verify Claude Code would actually route to this skill when a user types those phrases.

**Source**: Run 1 RED_TEAM blind spot B5.

**Estimate**: ½ day to design a routing test fixture (probably requires invoking a Claude subagent with the trigger phrase and asserting the right skill loads).

### K5 — c2 grep verification trivially gameable by keyword stuffing
The goal.md c2 verification uses `grep -c` for 11-item / Phase 0-7 keywords. A SKILL.md could trivially pass by listing keywords without semantic structure.

**Source**: Run 1 RED_TEAM finding F6.

**Estimate**: 30 minutes to extend `audit.py` to require Phase 0-7 as actual `## Phase N:` h2 headings with non-empty content under each.

### K6 — Upstream gbrain skillify drift detection
The fork is a one-time copy at upstream v1.1.0. If upstream changes the 11-item checklist or restructures phases, we won't know without manual review. A `scripts/check_upstream_drift.py` could pin the upstream commit hash and diff structure on demand.

**Source**: Run 1 RED_TEAM blind spot B2; aligns with closed-loop-skill-improvement wiki pattern's "verifier drift" failure mode.

**Estimate**: 1 hour for a script that fetches upstream + compares heading/checklist structure.

### K7 — `cross_modal_status='stale'` path has no production e2e
The audit logic handles the stale-receipt case (file changed since receipt was written), but we haven't actually produced a stale receipt in production and audited from there.

**Source**: Implicit gap; not directly RED_TEAM-flagged.

**Estimate**: 30 minutes; can be combined with K1 implementation.

---

## 📋 v2 scope (explicitly deferred)

### V1 — Claude Code plugin wrapper layer
`plugin.json` + `commands/skillify.md` so users can invoke `/skillify check ./SKILL.md` as a slash command.

**Source**: Run 1 alignment decision (defer to v2).

### V2 — Auto-fix LLM agency inside cross_modal_eval cycle loop
`cross_modal_eval.py --cycles 2` is currently no-op-on-fail; cycle 2 re-runs but doesn't apply fixes. v2 could have cycle 2 actually apply the cycle-1 improvements via an LLM call before re-scoring.

**Source**: `scripts/cross_modal_eval.py` docstring; closed-loop wiki article notes /automl supplies this externally for now.

### V3 — Upstream gbrain skillify sync mechanism
Beyond K6 (drift detection), a mechanism to selectively cherry-pick upstream improvements.

**Source**: Run 1 out-of-scope.

### V4 — PyPI listing + CI
GitHub Actions test matrix across 3 platforms; PyPI publication.

**Source**: Run 1 polish-level decision (MVP, no CI/PyPI).

### V5 — Formal CONTRIBUTING.md
Defer until first external contributor signals.

**Source**: Run 1 polish-level decision.

---

## 💭 Open design questions

### Q1 — Should `--emit RESOLVER.md` become the default?
Trigger: 2 months of OSS adoption + user feedback requesting a central registry.

### Q2 — Should `cross_modal_eval --cycles` default to 1 or 2?
Trigger: observation of whether cycle 2 ever produces materially different results given current no-op-on-fail behavior.

### Q3 — Slot B fallback chain order
Currently `codex-dispatch → openai → gemini → raw codex`. Trigger: OSS user feedback on which fallback most frequently activates.

### Q4 — Should the 5 scoring dimensions expand?
Candidates: completeness, anti-pattern compliance, upstream parity. Trigger: ≥20 skills audited with current 5 dimensions to see whether they're discriminative or saturated.

---

## 🐛 Dogfood candidates

Run `python3 -m scripts.audit <skill.md> --json` against these to surface heuristic gaps in skillify itself:

### D1 — srt skill (~/dev/srt-skill)
Python + extracted inline scripts + prompts/. Likely surface: script-extraction pattern detection, prompts/ directory recognition.

### D2 — polish skill
Pure rules in `references/writing-style.md`, no scripts. Tests `code_present` na-handling.

### D3 — codex-dispatch skill (~/.claude/skills/codex-dispatch)
Meta: skillify evaluating a skill that skillify depends on. Watch for circular reasoning.

### D4 — automl skill (~/.claude/skills/automl)
45 files. Stress test scaffold scan + check-resolvable on large skill.

Past dogfood results: **ghkb** (run 3 — robustness 7→8, error-handling gap closed); **skillify itself** (run 4 — verb workflow added, dimensions unchanged 9/9/9/8/9).

---

## 🌱 Article-derived (Garry Tan's introduction article)

Surfaced from comparing this fork's SKILL.md against Garry's introduction article (Readwise Reader shared id `01krcz9sbp6p9x9fmb7bfmmzf7`).

### N1 — "Skillify as a verb" SKILL.md section ✅ done (run 4)
### N2 — `scripts/skillify_it.py` thin orchestration wrapper ✅ done (run 4)

### N3 — README adds "latent vs deterministic" philosophy paragraph
Garry's distinction between latent (LLM judgment) and deterministic (fixed I/O) work is the conceptual underpinning of skillify. Our README doesn't explain why this distinction matters or how it shapes Phase 0 decisions.

### N4 — Add "search conversation for 'wtf'" eval heuristic
Garry: "search your conversation history for when you said 'fucking shit' or 'wtf' — those are the test cases you're missing." Add this to the LLM evals section as a discoverability heuristic for which user-facing failures need eval coverage.

### N5 — Daily eval cron
Garry runs 35 evals daily across his skills. Defer to v2; requires a `skillify doctor` equivalent of `gbrain doctor`.

### N6 — Cross-link N3 with the deterministic-surface Phase 0 criterion (N13)
N3 explains the concept; N13 applies it as a Phase 0 gate.

### N7 — SKILL.md adds a quick-start TL;DR (3-5 commands)
Run 4 post-edit cross-modal eval surfaced this from Slot A: current SKILL.md forces linear reading of Phase 0-7 before action.

### N8 — Resolve Phase 3 "quality gate" vs "informational" naming tension
Inherited from upstream v1.1.0: SKILL.md describes Phase 3 as "THE QUALITY GATE" while the audit contract treats item 3 as informational, non-blocking. The tension is real and confuses readers. Either rename to "Recommended quality check" or promote cross_modal_eval to blocking (with env-aware override already in place).

**Source**: Run 4 post-edit cross-modal eval, both slots independently flagged this.

### N9 — `cross_modal_eval` CLI flag consistency
Some examples use `--task`, some use the older `--output` alias for positional skill_path. Align documentation.

**Source**: Run 4 post-edit cross-modal eval, Slot B observation.

### N10 — Deterministic-vs-latent worked example
SKILL.md verb section table shows examples but not the reasoning that produced the split. Add one full walkthrough showing how a candidate workflow was correctly partitioned.

**Source**: Run 4 post-edit cross-modal eval, Slot A observation.

### N11 — Verb section adds Phase 0 pre-flight check
Before invoking `skillify_it.py`, the LLM should explicitly run Phase 0 self-check (should-this-be-a-skill criteria). The verb workflow currently jumps to scaffolding; the e2e test showed this skip can scaffold workflows that shouldn't have become skills.

**Source**: e2e test of verb workflow on this session itself (2026-05-12).

### N12 — Verb section adds retraction path
After `skillify_it.py` scaffolds + audits, the user may decide not to promote (e.g., audit revealed thin deterministic surface). Document the `rm -rf <skill-dir>` retraction explicitly and when to choose it.

**Source**: e2e test of verb workflow on this session.

### N13 — Phase 0 adds "reusable deterministic surface > 30%" criterion
Current Phase 0 (invoked 2+ times? >20 lines? clear trigger?) can all be marginal-yes while the underlying workflow is wrong-shape for a skill. Pure-latent workflows should be wiki patterns, not skills. A skill that's >70% prose-discipline carries skill maintenance overhead without the leverage benefit.

**Source**: e2e test on `skill-fork-and-dogfood-loop` candidate — passed Phase 0 marginally on the first three criteria but the right home was a wiki pattern (`wiki/closed-loop-skill-improvement.md` in the For_Claude knowledge base).

---

## Maintenance

This BACKLOG.md is updated as new findings surface from:
- RED_TEAM rounds in `/automl` runs
- Dogfood targets (D1-D4)
- External user reports
- Periodic upstream drift check (K6)

Closed items are kept with their resolution noted (e.g., "✅ done (run 4)") so the history stays auditable. Items are not deleted on completion.
