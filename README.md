# skillify — the meta skill (standalone fork)

`skillify` is a Claude Code skill that turns any raw feature into a properly-skilled, tested, resolvable unit of agent capability. It enforces an 11-item completeness checklist over a Phase 0–7 workflow, and uses a 2-evaluator cross-modal eval gate to prove output quality before tests lock behavior in.

This repo is a **standalone fork of [`garrytan/gbrain`](https://github.com/garrytan/gbrain) skillify v1.1.0**, decoupled from the gbrain CLI / brain framework so it runs as a self-contained Claude Code skill on macOS, Linux, and Windows.

> **Status:** MVP. README + LICENSE + sample-run polish only — no CI, no PyPI listing, no SLA. Issues welcome; responses are best-effort. Plugin wrapper layer is deferred to v2.

## Why this fork

Upstream skillify is excellent but coupled to the gbrain Bun/TypeScript CLI and the personal `~/.gbrain/` brain framework. To use it standalone you needed to install gbrain first. This fork:

- Replaces `gbrain skillify ...` CLI commands with pure Python scripts (`scripts/audit.py`, `scripts/scaffold.py`, etc.).
- Replaces the 3-evaluator upstream cross-modal eval with a 2-evaluator design: Slot A (Claude Code subscription) plus Slot B (auto-detect fallback chain). One mandatory Claude Code evaluator, one best-available second opinion.
- Stores eval receipts in `platformdirs.user_cache_dir("skillify")` instead of `~/.gbrain/.gbrain/eval-receipts/`.
- Adapts Phase 5 (Resolver) to Claude Code's description-based routing — dynamic scan of installed skills by default, optional `--emit RESOLVER.md` for users who want a static central registry.
- Adapts Phase 6 (Brain filing) to a generalized "any persistent location requires filing entry in SKILL.md" check, removing gbrain-specific brain coupling.

## Install

### Prerequisites

- Python 3.10 or newer.
- Claude Code installed (so the skill loads from `~/.claude/skills/`).
- Claude Code CLI `claude` on PATH for the Slot A subprocess fallback.
- At least one Slot B option: `OPENAI_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, OpenAI Codex CLI `codex` on PATH, or the `codex-dispatch` Claude Code skill.

### macOS / Linux

```bash
git clone https://github.com/fredchu/skillify-skill.git ~/dev/skillify-skill
cd ~/dev/skillify-skill
pip install -e .
ln -s ~/dev/skillify-skill ~/.claude/skills/skillify
```

Optional providers:

```bash
pip install -e '.[all]'   # installs openai + google-generativeai
```

### Windows (PowerShell)

```powershell
git clone https://github.com/fredchu/skillify-skill.git $HOME\dev\skillify-skill
cd $HOME\dev\skillify-skill
pip install -e .
# Symlink (Developer Mode enabled, or run elevated):
New-Item -ItemType SymbolicLink -Path "$HOME\.claude\skills\skillify" -Target "$HOME\dev\skillify-skill"
```

If symlinks are restricted, copy the directory instead — Claude Code reads either form.

### Verify install

In a Claude Code session:

```
> claude /doctor
```

Look for `skillify` in the loaded-skills list with no errors.

## Configure

### Slot A — Claude Code subscription

**Slot A** — Claude Code (subscription). Two paths: (a) when invoked from a CC main session, the LLM uses the Agent tool to spawn an evaluator subagent (preferred — no CLI spawn overhead); (b) when invoked from a non-CC shell, the Python adapter (`scripts/slots/slot_a_claude_code.py`) calls subprocess `claude --print`. Both paths bill against your Claude Code subscription quota. Requires the `claude` CLI on PATH for the subprocess fallback (`shutil.which("claude")`).

### Slot B — fallback chain (auto-detects first available, in order)

1. **`codex-dispatch` skill** — if you have OpenAI Codex CLI authenticated and the codex-dispatch Claude Code skill installed.
2. **OpenAI SDK** — set `OPENAI_API_KEY`.
3. **Gemini SDK** — set `GOOGLE_GENERATIVE_AI_API_KEY`.
4. **Raw `codex exec`** — fallback to direct subprocess call if Codex CLI is on PATH.

You only need ONE Slot B to be available. The eval will still run with Slot A alone (degraded — you lose cross-provider blind-spot coverage), and the audit verdict will note `slot_b: unavailable`.

## Usage

`skillify` is invoked as a Claude Code skill. Real triggers users type:

- `skillify this`
- `is this a skill?`
- `make this proper`
- `check skill completeness`

It walks Phase 0 through Phase 7 and emits an audit verdict (`properly skilled` / `close` / `needs skillify`).

You can also invoke the underlying scripts directly for ad-hoc audits or scaffolding:

```bash
# Audit an existing skill
python3 -m scripts.audit ~/.claude/skills/my-skill/SKILL.md --json

# Scaffold a new skill
python3 -m scripts.scaffold my-new-skill

# Check resolver collisions across all installed skills (dynamic scan default)
python3 -m scripts.check_resolvable

# Optional: export a static RESOLVER.md
python3 -m scripts.check_resolvable --emit RESOLVER.md

# Run cross-modal eval with default 2 cycles
python3 -m scripts.cross_modal_eval --task "..." --output ~/.claude/skills/my-skill/SKILL.md
```

## Upstream attribution

This skill is a fork of the `skillify` skill from [`garrytan/gbrain`](https://github.com/garrytan/gbrain) (commit pinned at fork time inside `SKILL.md`'s "Upstream attribution" section). The upstream project is MIT licensed. This fork preserves the original copyright and adds Fred Chu's copyright for the standalone-port additions. See `LICENSE` for the full text.

The fork is one-shot — we don't currently sync upstream changes back. If upstream skillify ships a meaningful improvement, file an issue and we'll evaluate porting it.

## Status

This is an MVP polish targeted at one-friend onboarding (a Windows user) plus the broader Claude Code OSS community as a discovery audience. Concretely:

- Slot A uses Claude Code subscription quota through the Agent tool or `claude --print` CLI fallback. Slot B providers each have an integration smoke test but the fallback chain hasn't been stress-tested under quota exhaustion.
- No CI / GitHub Actions / PyPI release workflow. To upgrade, `git pull` and `pip install -e .` again.
- Issues and PRs welcome. No SLA — best-effort responses.

## License

MIT. See [`LICENSE`](LICENSE).
