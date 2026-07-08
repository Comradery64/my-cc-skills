# Frugal Fable — mid-task cheatsheet

## Two levers, in order

1. **Effort first.** Default `low`. Escalate only on a signal (failed gate, low-confidence return, stopped-short slice, review mismatch). Never start high "to be safe." **Caveat:** the low-is-nearly-free evidence is strong on SWE-bench-shaped work (flat curve) and weak on hard/novel agentic-repo work (steep curve — low ≈ 1/3 of achievable quality on FrontierCode). Still start low, but treat low on those slices as a known gamble: instrument + lean on verify, or log an upward override if you have a prior.
2. **Delegation second.** Route heavy, verifiable work to cheaper models; judgment stays with Fable.

## Orchestrator's own effort = by phase (not by session)

| Phase (never delegated) | Effort |
|---|---|
| Decompose a fuzzy problem | high |
| Integrate clean, pre-verified patches | low |
| Final review | scale to what's shipping |

Phase is always knowable when you enter it — this is never a guess.

## Route each slice (highest axis sets model + effort floor; go up, never down)

- Stakes ↑ (ships / architectural / security) · Reversibility ↑ (one-way / hard to test) · Ambiguity ↑ (needs judgment → Fable)

| Slice | Model | Effort floor |
|---|---|---|
| scan / grep / inventory / log + test-output reduction / doc summary | Haiku | low |
| bounded patch (well-specified) / adversarial verify / targeted tests | Sonnet (build+tests must pass) | low–medium |
| hard refactor / correctness- or security-critical / Sonnet struggled | Opus (Fable reviews diff) | medium |
| decompose / architect / coordinate shared files / integrate / final review | Fable (never delegate) | per phase above |

Conservative floor: architectural/high-stakes/one-way → Opus or Fable only. Unsure about tier OR effort → go up one.

**Hybrid routing:** the table is the static FLOOR, not a runtime free choice. Override a slice UPWARD only, with a logged `reason` (`override: { tier: 'opus', reason: '...' }`). Downward overrides are clamped back to the floor. Raise-only + logged = auditable.

## Escalate on a signal, not a hunch

Re-run a slice higher (effort, then tier) ONLY when: verification gate failed · return came back `confidence: low` · slice `stoppedShort` · review finds output ≠ spec. A targeted re-run beats running everything high.

**Classifier block ≠ quality signal.** If a Fable-served slice trips a safety classifier (cyber/bio-chem/distillation), bumping effort just re-blocks. On the API the default is BLOCK, not auto-fallback. Fix = model SWAP to Opus at same effort (template does this once, tags `swappedToOpus`; if Opus also blocks → `needsFable`, no result). Infra/security work trips the cyber classifier more; card publishes no benign-FP rate — expect occasional spurious blocks.

## Context firewall

Delegated agent writes to `.frugal-fable/<task>/` and returns ONLY: `path + 3-line summary + confidence`.
Fable reads files on demand at synthesis/review — never pulls all output into context up front.

## Harness

1 slice / coupled / interactive → Fable direct. Few independent → inline `Agent`. Many independent → `Workflow` (out-of-context). Research → `frugal-research` (capped) or `deep-research-cheap` (headroom).

## Handoff packet (every delegation)

objective + repo path · in-scope / out-of-scope · **effort floor** · where to write + what to return (path+summary+confidence, not full content) · verification commands + success criteria · stop conditions (mismatch / failed retry / needs out-of-scope → stop & report).

## Quality gate

No delegated patch accepted until it passes the verification its stakes demand. Fable integrates + reviews the diff. Reports are leads, not facts — reopen cited files before relying on high-impact findings.

## First-time vs repeat

Novel work can't be priced upfront — instrument it (`/usage`, then record the miss to memory). Familiar shapes ARE predictable from the prior. The prediction problem decays with every repeat.

## Research tooling

`bdata search` / `bdata scrape` over built-in web tools (broader reach, fewer blocks, writes to file). Fall back to WebSearch/WebFetch.
