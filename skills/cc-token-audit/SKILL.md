---
name: cc-token-audit
description: Audit a person's real Claude Code token usage and recommend which context-saving tool (context-mode, codebase-memory-mcp, cozempic, ponytail, rtk, or token-savior) — alone or paired — best fits their usage, then set up a $0 passive A/B to prove it on their real work. Use when someone asks to analyze/reduce their Claude Code token cost or context usage, find which token-saving tool/strategy fits them, audit where their CC spend goes, or evaluate rtk / context-mode / ponytail / codebase-memory-mcp / cozempic / token-savior for their own usage. Triggers on "analyze my Claude Code usage", "which token-saving tool should I use", "where is my CC spend going", "cut my context costs", "evaluate context-mode/rtk/ponytail/codebase-memory-mcp/cozempic/token-savior for me".
---

Audit someone's **real** Claude Code usage (default last 60 days), find where their
token cost actually goes, recommend the context-saving tool that targets *their*
dominant cost bucket, and validate it with a **passive** A/B on their real work.

## NON-NEGOTIABLE method guardrails

0. **$0 TOTAL — this skill spends no API money.** Every phase runs on **deterministic
   local tools only**: `ccusage`, `rtk`, and the `claude plugin` CLI (plugin
   management makes no model calls). The reading/recommending is done inline by the
   session already running this skill — no extra spend.
   - **FORBIDDEN inside this skill:** `claude -p` (any headless run), the Agent/Task
     tool, the Workflow tool, or any spawned sub-agent. Those make model calls, so
     they cost API money and break the $0 guarantee.
   - **If a step genuinely needs LLM intelligence** (e.g. richer usage-pattern
     reasoning beyond the rule-based cost-structure mapping): do it **inline in the
     current interactive session**, and **strictly on Sonnet** (never Opus, never a
     spawned model). Prefer extending the deterministic scripts over adding any model
     step. If you cannot do it for $0 on Sonnet interactively, **don't do it** —
     report what the free analysis shows instead.

1. **ccusage is ground truth for $.** NEVER estimate cost by summing
   `usage` tokens × full API rates — that inflates the real bill 3–6× (mixed models,
   subscription pricing, double-counted cache reads). Always anchor $ to ccusage.
2. **Measure savings with a passive A/B, not headless replays.** Headless `claude -p`
   replays are non-interactive (zero-shot, no steering), so they don't represent how
   an end user actually drives Claude Code and produce unrepresentative savings numbers
   — on top of costing API money. The valid measurement is **passive**: enable a tool
   during normal interactive use and compare recorded usage windows.
3. **Match the tool to the cost structure**, not to marketing:
   - **context/cache dominates** (typical — usually the plurality of cost) → **context-mode**.
     Be precise about what it actually does (verified from its hooks + code): it **indexes
     tool outputs for recall** (`ctx_search`) + **auto-redirects `curl`/`wget`** to a sandbox.
     It does **NOT auto-compress the current context** — ordinary `Read`/`Bash` pass through
     with advisory tips only. So it only cuts cache_read when the agent actually uses its
     `ctx_*` tools *at the source* (`ctx_execute_file` over `Read`, `ctx_batch_execute` over
     N command runs). It's a **behavioral lever, not a magic compressor** — don't promise it
     will halve cache_read alone; pair it with codebase-memory-mcp, and if it's already installed, the
     advice is "use it," not "install it" (the analyzer tags `[ALREADY INSTALLED]`).
   - **context/cache dominates AND fresh-input share is high on a large repo** (lots of
     grep/Read file-discovery) → **codebase-memory-mcp** (a tree-sitter knowledge-graph
     MCP: indexes the repo to functions/classes/call-chains across 158 langs + Hybrid
     LSP semantic types; sub-ms structural queries + cross-repo edges. One query
     replaces dozens of grep/Read cycles — its bench shows ~99% fewer tokens on
     structural queries). Attacks the same bucket from the *input* side, so it
     **pairs** with context-mode rather than replacing it.
   - **context/cache dominates AND read-only recall isn't enough** → **cozempic**
     (active pruning — 18 strategies trim stale reads, old tool results by age,
     thinking blocks, duplicate reminders, >8KB tool outputs; a 4-tier auto-guard
     reloads the session). This is the "auto-compress current context" that
     context-mode does NOT do — the most direct attack on re-cached bloat.
     **Higher-risk:** it MUTATES transcripts + reloads the Claude process (brittle
     on forks / non-stock configs, esp. with custom `CLAUDE_CODE_*` compaction env
     or Agent Teams) and auto-updates on SessionStart. Escalate to this *after* the
     read-only tools; on forks, disable the auto-updater + reconcile its thresholds
     with your compaction env first.
   - **output dominates** → **ponytail** (lazy-senior-dev rules → writes less code).
   - **many noisy shell commands** → **rtk** (compresses CLI output). Usually a small
     lever; quantify it, don't assume.
   - **wants one install covering several buckets** → **token-savior** (an MCP that
     bundles symbol indexing + 34 bash-output compactors + cross-session memory).
     Consider it *instead of* stacking context-mode + codebase-memory-mcp + rtk — but it's a
     persistent MCP that adds manifest tokens every session, so measure that overhead
     in the A/B rather than assuming net savings.
   - **Pairings**: the analyzer surfaces complementary combos when the numbers justify
     them (e.g. context-mode + codebase-memory-mcp = offload big outputs *and* stop re-reading
     files; context-mode + ponytail = smaller context *and* less generated code). Note
     codebase-memory-mcp/token-savior are **local MCP servers** (no remote proxy, no data
     exfiltration) — installing an MCP makes no model calls, so it stays $0.
4. **Everything in Phases 1–2 is $0** (local log analysis). The A/B's only marginal
   cost is the tool's overhead on work the person does anyway.

## Dependencies (the skill installs tools lazily — one per A/B)
- **ccusage** (the measurement instrument): `npm i -g ccusage` or it falls back to
  `npx -y ccusage@latest`. Needs Node.js ≥18.
- **claude CLI** with the `plugin` subcommand (context-mode/ponytail/cozempic) and
  the `mcp` subcommand (codebase-memory-mcp/token-savior).
- **git** (marketplace add pulls from GitHub); **Homebrew or cargo** (only if testing
  rtk); **curl/bash** (codebase-memory-mcp — static binary, zero runtime deps); **python3/pip** (token-savior, cozempic).
- The five tool repos are **not pre-bundled**; `scripts/setup_tool.sh <tool>` clones/
  installs only the tool being tested, on demand. Run `setup_tool.sh --check` first.

## Phase 1 — Baseline (free, instant)
Run the analyzer (it auto-finds ccusage or uses npx):
```
python3 {SKILL_DIR}/scripts/baseline.py --days 60
```
It reports: real spend (ccusage), token-volume shares, approximate cost-share by
bucket (cache_read / cache_create / output / input), top projects by cost, and the
dominant cost bucket. Read the dominant bucket — that determines the recommendation.

If ccusage is missing: `npm i -g ccusage` (or it falls back to `npx -y ccusage@latest`).

**If spend shows $0 / "0 sessions":** the user likely runs a **redirected config**
(`CLAUDE_CONFIG_DIR` — common with forks/mirrors like cc-mirror). ccusage reads
`~/.claude/` by default; their real usage lives elsewhere. Prefix the run with
their config root, e.g. `CLAUDE_CONFIG_DIR=~/.cc-mirror/zai/config python3 baseline.py --days 60`.
The analyzer also **auto-falls back to `ccusage daily`** when `ccusage session`
returns 0 (a known ccusage limitation with some transcript formats / config
redirects) — daily mode drops the per-project + headless split but keeps the
cost-bucket analysis that drives the recommendation. `compare.py` falls back the
same way (per-day aggregates, noisier than per-session).

## Phase 2 — Tool-fit diagnosis (free)
The analyzer prints a ranked recommendation from the person's actual numbers. Then
quantify rtk's concrete ceiling on their real history (also $0, local):
```
rtk cc-economics              # realized savings + spend (if rtk installed)
rtk discover --all --since 60 # missed savings rtk WOULD capture, by command
```
Present: "Your spend is ~X% context/cache, Y% output, Z% CLI-shaped. The tool that
targets your biggest bucket is **<tool>**." Be honest when a popular tool (e.g. rtk)
barely moves their bill — report the real number.

## Phase 3 — Passive A/B setup (free)
**Install only the ONE recommended tool** (lazy — don't clone all three). The setup
script handles the dependency (Homebrew formula for rtk; `claude plugin marketplace
add` + install + enable for the plugins) idempotently:
```
{SKILL_DIR}/scripts/setup_tool.sh --check          # see what's already present
{SKILL_DIR}/scripts/setup_tool.sh context-mode     # install + enable the #1 pick
```
It maps each tool to its real source: **rtk** → `brew install rtk` (or `cargo`) +
`rtk init -g`; **context-mode** → marketplace `mksglu/context-mode`; **ponytail** →
marketplace `DietrichGebert/ponytail`; **codebase-memory-mcp** → `curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash`
+ `codebase-memory-mcp install -y` (then say "Index this project" in Claude, or the `index_repository` MCP tool); **token-savior**
→ `pip install "token-savior-recall[mcp]"` + `claude mcp add token-savior`. Because
installing/enabling a plugin or MCP mutates the person's global Claude Code config,
**confirm with them before running setup** (or have them run it). Then record the start
and use CC normally ~1–2 weeks:
```
python3 {SKILL_DIR}/scripts/compare.py --enable <recommended-tool>
```
To end the test: `{SKILL_DIR}/scripts/setup_tool.sh <tool> --disable`.

## Phase 4 — Measure & report (after the window)
```
python3 {SKILL_DIR}/scripts/compare.py                  # before/after around the marked date
python3 {SKILL_DIR}/scripts/compare.py --project <repo> # like-for-like (best signal)
python3 {SKILL_DIR}/scripts/compare.py --model opus-4-8 # control for model mix
```
Report Δ cost/session and Δ cacheRead/session. **Caveat the noise**: trust only with
n≳15 sessions each side and a `--project` filter (the work a person does varies week
to week; that confound shrinks with a project filter + longer `--window`, never fully
vanishes — but it's far more valid than any replay).

## Output
A short per-person verdict: where their money goes, the recommended tool *with their
own numbers*, and — after the A/B — the measured real-usage delta. If a tool doesn't
help them, say so plainly.

## Notes
- `{SKILL_DIR}` = this skill's directory. `enabled.json` (written by `--enable`) holds
  the A/B cutoff; it's per-machine state.
- Portable: scripts hardcode no user paths and read the standard CC log location ccusage uses.
- Background/origin: distilled from a full eval on netcup (`eval/cctok/`); this skill
  uses the $0, passive-measurement method rather than headless replays.
