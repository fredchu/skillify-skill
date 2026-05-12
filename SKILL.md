---
name: skillify
version: 0.1.0
description: |
  The meta skill — turn any raw feature into a properly-skilled, tested,
  resolvable unit of agent capability. Enforces an 11-item completeness
  checklist over a Phase 0-7 workflow. Cross-modal eval (Phase 3) is the
  recommended quality gate: 2 frontier models from different providers
  critique the output, you iterate to quality, THEN write tests that lock
  in the proven-good behavior. Standalone fork of garrytan/gbrain skillify
  v1.1.0 — runs without the gbrain CLI / brain framework.

  Use when the user says: "skillify this", "skillify", "is this a skill?",
  "make this proper", "add tests and evals for this", "check skill
  completeness", "audit this skill", or wants to scaffold a new skill from
  an existing script.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
mutating: true
---

# Skillify — The Meta Skill

## Upstream attribution

This skill is a standalone fork of [`garrytan/gbrain`](https://github.com/garrytan/gbrain) `skillify` v1.1.0 (MIT licensed). The original 11-item checklist, Phase 0-7 workflow, anti-patterns list, and worked example are preserved verbatim where the substance survived the port. Adaptations from upstream:

- `gbrain skillify ...` CLI commands → pure Python scripts (`scripts/audit.py`, `scripts/scaffold.py`, `scripts/check_resolvable.py`, `scripts/cross_modal_eval.py`).
- 3-evaluator upstream cross-modal eval → 2-evaluator (Slot A: Claude Code subscription; Slot B: codex-dispatch → OpenAI → Gemini → raw codex fallback chain).
- `~/.gbrain/.gbrain/eval-receipts/` → `platformdirs.user_cache_dir("skillify")`.
- Phase 5 Resolver: dynamic scan of installed skills by default + optional `--emit RESOLVER.md`.
- Phase 6 Brain filing: generalized to "any persistent location requires filing entry in SKILL.md".

> **Relationship to `/cross-modal-review`:** That skill (when present) is the manual mid-flow "second opinion" gate (one model reviews work product before commit). This skill's Phase 3 below uses the local `scripts/cross_modal_eval.py` instead — two different-provider frontier models score-and-iterate on a documented dimension list *before* tests cement behavior. Use `/cross-modal-review` for ad-hoc second opinions; use Phase 3 here when skillifying a feature.

## Contract

A feature is "properly skilled" when all 11 checklist items pass. Item 3 (cross-modal eval) is informational — it does not gate the audit verdict, but a missing or stale receipt is surfaced so the user knows where the gate stands.

## The Checklist

```
□ 1.  SKILL.md           — skill file with frontmatter + contract + phases
□ 2.  Code               — deterministic script if applicable
□ 3.  Cross-modal eval   — 2 frontier models from 2 providers; informational
□ 4.  Unit tests         — cover every branch of deterministic logic
□ 5.  Integration tests  — exercise live endpoints
□ 6.  LLM evals          — quality/correctness cases for LLM-involving steps
□ 7.  Resolver trigger   — description field has real user trigger phrases
□ 8.  Resolver eval      — test that triggers route to this skill
□ 9.  Check-resolvable   — DRY + MECE audit, no orphans, no collisions
□ 10. E2E test           — smoke test: trigger → side effect
□ 11. Brain filing       — if it writes to any persistent location, declare it in SKILL.md
```

## Phase 0: Should This Be a Skill?

Before skillifying, check:

- Will this be invoked 2+ times? (One-off work ≠ skill)
- Is there >20 lines of logic? (Trivial helpers don't need full infrastructure)
- Does it have a clear trigger phrase a user would actually say?

If no to all three, it's a script, not a skill. Move on.

## Phase 1: Audit

```
Feature: [name]
Code: [path]
Missing items: [check each of the 11]
```

Run:

```bash
python3 -m scripts.audit <path-to-SKILL.md> --json
```

The output reports per-item status (`pass` / `fail` / `n/a`) and an overall verdict.

## Phase 2: Write SKILL.md + Code (items 1-2)

### SKILL.md frontmatter template (copy-paste):

```yaml
---
name: my-skill
version: 0.1.0
description: |
  One paragraph. What it does, when to use it, real user trigger phrases
  in the prose (Claude Code routes by description matching).
allowed-tools:
  - Bash
  - Read
  - Write
mutating: false  # true if it writes to any persistent location
---
```

Body must include: **Contract** (what it guarantees), **Phases** (step-by-step), **Output Format** (what it produces).

Extract deterministic code into `scripts/*.py`. Use the scaffolder:

```bash
python3 -m scripts.scaffold my-new-skill
```

This creates `~/.claude/skills/my-new-skill/{SKILL.md, scripts/, test/}` with a starter template that already passes Phase 1 audit.

## Phase 3: Cross-Modal Eval (item 3) — THE QUALITY GATE

### LLM-driven invocation (preferred when in a Claude Code session)

When this skill is invoked from within a Claude Code main session (the
typical case), the main-session LLM SHOULD prefer the Agent tool to spawn
two evaluator subagents (Slot A + first-available Slot B) rather than
falling through to the Python adapter's subprocess path. The Agent-tool
flow:

1. Read SKILL.md being evaluated; build the prompt via
   `scripts.slots.base.build_eval_prompt(skill_text, task_description)`
2. Spawn Slot A subagent (Agent tool, general-purpose, opus) with the
   prompt; expect JSON in the reply
3. Spawn Slot B subagent (auto-detect via codex-dispatch / openai SDK /
   gemini SDK / raw codex) with the same prompt
4. Parse both replies via `scripts.slots.base.parse_score_json`
5. Aggregate via `scripts.aggregator.aggregate`
6. Write receipt via `scripts.receipt.write_receipt`

The Python adapter path (subprocess `claude --print` via
`ClaudeCodeSlotA.score()`) is the fallback when this skill is invoked
from a non-CC shell (e.g. `python3 -m scripts.cross_modal_eval` from
plain bash). Both paths bill against the Claude Code subscription;
neither uses the per-token Anthropic API.

### Why this comes before tests

Tests lock in behavior. If the behavior is mediocre, tests lock in mediocrity. Cross-modal eval proves the quality bar FIRST, then tests cement it.

### Step 1: Pick a representative input

Choose the input that exercises the skill's hardest documented use case. If unsure: use the primary trigger example from SKILL.md, or the most complex real-world input from the last 7 days of memory files.

### Step 2: Run the skill, capture output

Run the skill on the representative input. The OUTPUT FILE is what gets evaluated.

### Step 3: Run the eval gate

```bash
python3 -m scripts.cross_modal_eval \
  --task "What this skill is supposed to accomplish" \
  --output ~/.claude/skills/<slug>/SKILL.md
```

The command runs 2 frontier models from 2 different providers (Slot A + Slot B), scores the OUTPUT against the TASK on 5 documented dimensions, and writes a receipt under `platformdirs.user_cache_dir("skillify")/<slug>-<sha8>.json`. The sha-8 binds the receipt to the current SKILL.md content — re-running after edits writes a new receipt.

**Slot configuration:**

| Slot | Model | Provider | Required |
|------|-------|----------|----------|
| A | `claude-code-cli` | Claude Code subscription / `claude` CLI | Yes |
| B | `codex-dispatch` → OpenAI → Gemini → raw `codex` (auto-detect first available) | varies | Yes (any one) |

**These MUST be from DIFFERENT providers.** Different families have less correlated blind spots — that's the whole point of cross-modal eval. Refresh the model picks when a new generation ships.

**5 scoring dimensions** (each 0-10):

1. **Goal achievement** — does the output accomplish what the task says?
2. **Depth** — does it go beyond surface-level coverage?
3. **Specificity** — concrete details vs vague generalities?
4. **Robustness** — handles edge cases, failure modes?
5. **Trigger clarity** — would a user actually say the trigger phrases?

**Pass criteria (BOTH must be true):**

1. Per-dimension mean ≥ 7 across the 2 evaluators.
2. No single model scored any dimension < 5 (the floor).

**Split detection:** any dimension where the 2 models disagree by > 3 points is flagged for human review (compensates for the missing tie-breaker third evaluator vs upstream's 3-evaluator design).

**Inconclusive:** fewer than 2 of 2 models returned parseable scores. Receipt is still written (forensics) but the gate is not authoritative. Exit code 2.

### Step 4: Cycle until you pass (default `--cycles 2`)

```
CYCLE 1:
  Eval → scores + top improvements per dimension
  IF pass: → done, write tests
  ELSE:
    Apply top improvements to the actual file
    Log: which improvements applied, what changed

CYCLE 2 (default final):
  Re-eval the FIXED output (same models, same dimensions)
  Compare: before/after scores per dimension (track delta)
  IF pass: → ship
  ELSE: → ship with KNOWN_GAPS section listing:
    - Which dimensions are still below 7
    - Which improvements couldn't be resolved
    - Why (e.g., "would require architectural change")
```

Override with `--cycles 3` for harder skills; CI defaults to `--cycles 1`.

### Provider configuration

Slot A: Claude Code subscription. In a Claude Code main session, prefer the
Agent-tool flow above. From a non-CC shell, install/authenticate Claude Code
and ensure `claude` is on PATH, or set `SKILLIFY_CLAUDE_BIN` to the binary
name/path used by `shutil.which`.

Slot B (any one is enough; auto-detected in this order):

1. Have `codex-dispatch` skill installed + `codex` CLI authenticated → uses codex-dispatch.
2. `export OPENAI_API_KEY=sk-...` → uses OpenAI SDK directly.
3. `export GOOGLE_GENERATIVE_AI_API_KEY=...` → uses Gemini SDK directly.
4. `codex` on PATH but no above keys → falls back to raw `codex exec`.

### Cost expectations

2 cycles × 2 models = 4 frontier calls max per run. Slot A bills against Claude Code subscription quota; Slot B cost depends on the selected fallback provider. Receipts include per-call model identifiers for retroactive audit.

### Skip cross-modal eval when:

- Output is < 200 tokens (trivial — not worth 4 API calls).
- The skill is a thin wrapper around a single API call (one cycle is enough).

## Phase 4: Tests (items 4-6)

NOW that eval has proven quality, write tests that lock it in:

- **Unit tests** — every branch of deterministic logic. Mock external calls.
- **Integration tests** — hit real endpoints. Catch bugs mocks hide.
- **LLM evals** — quality/correctness for LLM steps. Lighter than cross-modal eval — test specific behaviors.

Run with `pytest` (this fork uses pytest, not upstream's `bun test`):

```bash
pytest test/
```

## Phase 5: Resolver trigger + Check-resolvable (items 7-9)

Claude Code routes invocations by matching user input against the `description` field in each skill's frontmatter. There is no central `RESOLVER.md` by default — the description field IS the resolver entry.

1. **Resolver trigger (item 7)**: SKILL.md `description` field includes real user trigger phrases (verbatim text users actually type) embedded in prose. Internal jargon doesn't route — mirror real user language.

2. **Resolver eval (item 8)**: feed sample user phrases through Claude Code's skill-routing layer (or a routing-eval JSONL fixture); assert the right skill activates.

3. **Check-resolvable (item 9)** — run:

   ```bash
   # Default: dynamic scan of all installed skills
   python3 -m scripts.check_resolvable

   # Optional: emit a static RESOLVER.md for users who want a central registry
   python3 -m scripts.check_resolvable --emit RESOLVER.md
   ```

   The script scans `~/.claude/skills/*/SKILL.md` plus `~/.claude/plugins/cache/*/skills/*/SKILL.md` and reports:

   - Description collisions (two skills claim the same trigger phrase)
   - DRY violations (shared logic copy-pasted across skills instead of imported)
   - Ambiguous trigger routing (one phrase plausibly hits multiple skills)
   - Orphans (skills with no real user-facing trigger in description)

## Phase 6: E2E + Persistent-location filing (items 10-11)

- **E2E smoke (item 10)**: full pipeline from trigger to side effect. Real input, real output, no mocks.

- **Persistent-location filing (item 11)**: if the skill writes to ANY persistent location (disk, cache, Apple Notes, Reader, git commit, etc.), SKILL.md must declare WHERE in an "Output" section. The audit greps for `Path.write_text`, `git commit`, `Write` tool calls, MCP write operations, etc. in scripts; if found and no Output declaration → fail. If skill writes nothing persistent, this item is N/A and does not block pass.

  Example Output declaration in SKILL.md body:

  ```markdown
  ## Output

  - Audit receipts: `platformdirs.user_cache_dir("skillify")/<slug>-<sha8>.json`
  - RESOLVER.md (when --emit flag used): writes to current working directory
  ```

## Phase 7: Verify

```bash
pytest test/                                                  # all tests green
python3 -m scripts.audit ~/.claude/skills/<slug>/SKILL.md --json | \
  python3 -c "import sys, json; d = json.load(sys.stdin); print(d['verdict'])"
ls "$(python3 -c 'from platformdirs import user_cache_dir; print(user_cache_dir(\"skillify\"))')"
python3 -m scripts.check_resolvable --json
```

Expected: `pytest` exits 0, audit verdict is `properly skilled` or `close`, receipt file exists, check-resolvable reports no collisions.

## Worked Example: Skillifying a "summarize-pr" Feature

```
Phase 0: Yes — invoked weekly, 50+ lines, clear trigger "summarize this PR"
Phase 1: Audit → SKILL.md missing, no tests, no resolver entry. Score: 1/11
Phase 2: python3 -m scripts.scaffold summarize-pr
         Edit SKILL.md to add real description + extract logic to scripts/summarize_pr.py
Phase 3: python3 -m scripts.cross_modal_eval --task "..." --output ~/.claude/skills/summarize-pr/SKILL.md
         Cycle 1 →
           Slot A (Claude Code): goal=7, depth=6, specificity=5 → "no test plan in summary"
           Slot B (codex-dispatch/GPT-4o): goal=6, depth=5, specificity=4 → "misses file-level diffs"
           Aggregate: goal=6.5 FAIL, depth=5.5 FAIL, specificity=4.5 FAIL+floor
           Top improvements: add file-level changes, include test plan, use PR context
         → Apply fixes → Cycle 2: goal=8, depth=7.5, specificity=7 → PASS
Phase 4: Write 12 unit tests locking in the improved behavior
Phase 5: description field already contains "summarize this PR"; check_resolvable: clean
Phase 6: E2E test: feed a real PR URL → verify summary file written; SKILL.md declares Output: ./pr-summaries/
Phase 7: All green. Score: 11/11
```

## Quality Gates

NOT properly skilled until:

- All required items pass (1-2, 4-10; 11 only when applicable).
- Cross-modal eval (item 3) has a current receipt OR is explicitly waived with rationale (item 3 is informational; not blocking, but a missing receipt is visible in the audit).
- All tests pass (unit + integration + LLM evals).
- Description field has real user trigger phrases.
- check-resolvable shows no collisions, overlaps, or DRY violations.
- Persistent-location filing if applicable.

## Output Format

Skillify produces three durable artifacts per skill:

1. **The skill tree on disk.** `~/.claude/skills/<slug>/SKILL.md`, `scripts/<slug>.py`, `test/test_<slug>.py` skeleton, optional `routing-eval.jsonl`. Generated by `python3 -m scripts.scaffold <name>` and refined by the human/agent into a real implementation.

2. **A cross-modal eval receipt** at `platformdirs.user_cache_dir("skillify")/<slug>-<sha8>.json`. The sha-8 binds the receipt to the current `SKILL.md` content. `python3 -m scripts.audit` surfaces the status (`found` / `stale` / `missing`) as informational.

3. **An audit verdict** from `python3 -m scripts.audit ... --json`:

   ```json
   {
     "verdict": "properly skilled" | "close" | "needs skillify",
     "score": "<passed>/<total>",
     "items": [{"name": "...", "status": "pass"|"fail"|"n/a", "detail": "..."}],
     "receipt_status": "found" | "stale" | "missing"
   }
   ```

   Required items gate the verdict; item 3 (cross-modal eval) is informational and never blocks PASS.

## Skillify as a verb

In addition to the explicit `python3 -m scripts.audit ...` and `python3 -m scripts.scaffold ...` flows above, skillify is designed to be invoked as a single verb mid-conversation. The pattern, adapted from Garry Tan's original article, is: prototype in conversation, see it work, say "skillify it", and turn the working procedure into durable skill infrastructure.

### Verb trigger phrases

Treat any of these user phrases as a possible verb-mode trigger:

- "skillify it"
- "make this permanent" or "make this a skill"
- "remember this as a skill" or "remember this as a <topic> skill"
- "next time we need to do this..." or "next time anyone needs X..."
- "let's turn this into a skill"

When the main-session LLM hears one of these and the recent conversation contains a substantive solution, workflow, or discovery that meets [Phase 0 criteria](#phase-0-should-this-be-a-skill), trigger the verb workflow below. Do not trigger on the verb alone if there is no substantive work to promote; idle "we could skillify that someday" language should wait for real material.

### Conversation-extraction protocol

The extraction is LLM-driven; `scripts/skillify_it.py` does not read chat logs or mine the conversation. When the verb fires, the main-session LLM extracts:

1. **Skill name** - a short kebab-case slug that captures the topic, such as `webhook-oauth`, `calendar-double-booking`, or `ngrok-verify`. If the user named it in the verb phrase, use that; otherwise propose one.
2. **Description** - one paragraph describing what the skill does, what failure mode it prevents, and when to invoke it. Mirror SKILL.md frontmatter style and include real trigger phrases in plain quotes; see [Phase 5](#phase-5-resolver-trigger--check-resolvable-items-7-9).
3. **Procedure** - the steps the user and agent just walked through, rewritten in instructive register. This becomes the SKILL.md body.
4. **Deterministic split** - identify which steps are deterministic, such as file operations, format conversion, fixed lookups, timestamp math, grep, or curl checks, versus latent work such as judgment, summarization, or taste. Deterministic parts should become `scripts/*.py` later; latent parts stay as SKILL.md prose. Name the future scripts and stub their call sites if the implementation is not written yet.
5. **Trigger phrases** - the actual user phrases that should route to this skill in the future, kept in their natural style.

The key distinction is latent vs deterministic work. The LLM should not keep doing deterministic work in latent space when the same input should produce the same output; it should write deterministic scripts and call them next time.

### Invocation

After extraction, invoke the orchestration entry point:

```bash
python3 -m scripts.skillify_it <name> [--target-dir ~/dev] [--description "..."] [--audit] [--json]
```

This is a thin wrapper around `scaffold` plus optional `audit`. `scaffold` creates the SKILL.md skeleton, `scripts/__init__.py`, and `test/test_smoke.py` at `<target_dir>/<name>/`. `--audit` then runs `audit_skill` on the freshly scaffolded skill and prints the verdict so the agent immediately sees what is still missing, often Phase 3 cross-modal eval, Phase 5 trigger clarity, or E2E proof.

The script does not perform the conversation extraction. It only makes the scaffold-then-audit chain feel like one step after the LLM has supplied the name and description.

### After scaffolding

The scaffold is only a skeleton. The LLM then:

- Fill in the SKILL.md body with the extracted procedure.
- Write deterministic scripts for the deterministic split, using TDD per [Phase 4](#phase-4-tests-items-4-6).
- Add the trigger phrases into the description.
- Run `python3 -m scripts.cross_modal_eval <skill>/SKILL.md` to populate the Phase 3 receipt.
- Re-run `python3 -m scripts.audit <skill>/SKILL.md` and check the verdict moves toward "properly skilled".

### Examples

| User says | Verb workflow extracts |
|---|---|
| "hot damn it worked. can you remember this as a webhook skill and skillify it, next time we need to do some webhooks?" | name=`webhook-oauth`, triggers=["next time we do webhooks", "OAuth callback flow"], procedure=the OAuth callback handler just debugged |
| "skillify it - next time anyone in openclaw needs a headless browser, route to playwright; for headed, ask user to run gstack browser" | name=`browser-path-selector`, triggers=["need a browser", "headless or headed", "scrape a site"], deterministic=which binary or command path to call, latent=headless-vs-headed decision |
| "make a skill, make it deterministic to check calendar double-bookings, tomorrow I have a double-booked 11am" | name=`calendar-double-booking`, triggers=["check my calendar", "any conflicts tomorrow"], deterministic=overlap-detection script, latent=which conflicts matter to flag |
| "can we make a skill that says whenever you send me a link you have to curl it yourself to make sure the endpoint is open and the tunnel works? skillify it!" | name=`ngrok-verify`, triggers=["send me a link", "verify the tunnel works"], deterministic=curl status and response check, latent=what evidence to summarize |

### Anti-patterns specific to verb mode

- ❌ Triggering on the verb without substantive material; the conversation must contain a workflow worth promoting.
- ❌ Calling `scripts/skillify_it.py` without first doing the LLM-driven extraction.
- ❌ Skipping the deterministic-vs-latent split; without that classification, the result is still just a prompt instead of a skill.

## Anti-Patterns

- ❌ Writing tests before cross-modal eval (locks in mediocrity)
- ❌ Using budget models for eval (C student grading A student)
- ❌ Using a single provider's family for both slots (correlated blind spots — the whole point of Slot A + Slot B is provider diversity)
- ❌ Skipping eval "because the output looks fine" (your judgment isn't 2 frontier models)
- ❌ Eval without fix cycle (vanity metrics)
- ❌ Code with no SKILL.md (invisible to resolver)
- ❌ Tests that reimplement production code (masks real bugs)
- ❌ Description field with internal jargon (must mirror real user language users actually type)
- ❌ Two skills doing the same thing (merge or kill one)
- ❌ Running cross-modal eval on trivial outputs (< 200 tokens, not worth 4 API calls)
- ❌ Writing to persistent locations without declaring in SKILL.md Output section (creates invisible side effects users can't audit)

## Output

This skill itself writes to:

- `platformdirs.user_cache_dir("skillify")` — eval receipts (JSON, sha-8 keyed).
- Current working directory — when `check_resolvable.py --emit RESOLVER.md` is invoked.
- `~/.claude/skills/<slug>/` — when `scaffold.py` creates a new skill tree.

All other operations are read-only (audit) or transient (cross-modal eval prompts).
