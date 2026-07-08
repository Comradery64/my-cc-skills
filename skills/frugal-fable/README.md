# Frugal Fable

Use when running on Claude Fable (or any premium model) and the work is token-heavy — building features, multi-file changes, research, testing, debugging, migrations, or anything spanning many files/sources.

**Two levers, applied in order:** (1) run Fable at the **lowest effort** that clears the bar and escalate only on a signal, and (2) delegate bounded, verifiable heavy-lifting to cheaper models — with a quality floor so construction is never owned by a weak agent.

## Why Frugal Fable?

Fable is expensive because Fable is good. There are two ways to overspend on it:
- Running it harder than the task needs
- Making it personally do work a cheaper agent could do

This skill attacks both **in that order** — effort first, delegation second — because effort is the primary cost dial and it applies to the orchestrator tokens you can't delegate away.

## The Deal

Run Fable at the lowest effort that clears the bar; escalate only when a concrete signal says you undershot. Cheaper agents *gather signal and produce candidate work to files*. Fable *decides, integrates, and reviews*. Truth-judgment and final quality stay with Fable, always.

## Key Concepts

### Lever 1: Effort First
**Default everything to `low`.** Lower-effort Fable still performs well and often exceeds high-effort prior models. Start there and let signals pull you up; do not start high "to be safe" — that is the single fastest way to burn your budget.

Escalate on a concrete signal (failed verification gate, low-confidence return, stopped-short slice, or review mismatch), never on a hunch.

### Lever 2: Delegation
Route heavy, verifiable work to cheaper models using a static routing table with raise-only overrides.

**What stays with Fable (never delegated):**
- Decomposing ambiguous work into clean, independent slices
- Architecture, product, and safety tradeoffs
- Shared-file coordination and integrating partial work
- Resolving conflicting subagent reports
- Final review, risk assessment, and synthesis

**Static routing floor** (Haiku → Sonnet → Opus → Fable):

| Slice Type | Model | Effort Floor |
|---|---|---|
| Scans, grep, inventory, log/test reduction, doc summaries | Haiku | low |
| Bounded patches, adversarial verification, targeted tests | Sonnet | low–medium |
| Hard refactors, correctness/security-critical code | Opus | medium |
| Decompose, architect, coordinate, integrate, final review | Fable | per phase |

## Quick Start

### ⚠️ Turn Ultracode OFF before using this skill

Frugal Fable and **Ultracode are opposites** and must not run together. Ultracode's standing order is *"run a workflow for every task, be exhaustive, loop until nothing is left."* Frugal Fable's whole purpose is to **conserve**. Run both and cheap workers fan out *and then* Fable launches exhaustive passes on top — exactly how usage gets blown.

**How to toggle Ultracode off:**
Use the toggle switch next to the model selector

### Essential Rules

1. **Decomposition prices the slices.** Score each on stakes/reversibility/ambiguity (you score these anyway) and read an effort floor off the same scores.

2. **Orchestrator effort follows the phase, not the session:**
   - Decompose a fuzzy problem → `high`
   - Integrate clean, pre-verified patches → `low`
   - Final review → scale to stakes

3. **Escalate on a signal, never on a hunch.** Re-run a slice higher only when something concrete fires.

4. **Context firewall:** Delegated agents write findings/patches to a scratch dir and return **only** path + 3-line summary + confidence. Fable reads files on demand at synthesis/review — never pulls all output into context up front.

## References

- **[SKILL.md](./SKILL.md)** — Full detailed guide covering all concepts, caveats, and patterns
- **[references/fanout-template.js](./references/fanout-template.js)** — Adaptable Workflow for fan-out: static routing floor + logged overrides, per-slice model and effort, adversarial verify, signal-driven escalation, classifier-block handling
- **[references/routing-cheatsheet.md](./references/routing-cheatsheet.md)** — One-screen routing table + effort ladder + firewall protocol for quick mid-task reference
- **[references/frugal-research.js](./references/frugal-research.js)** — Budget-capped research Workflow (Haiku collect → Sonnet verify → Sonnet synthesize, hard caps + token gate)

## Handoff Packet Template

Every delegation should include:
- Exact objective + repo path
- In-scope / out-of-scope files
- **Effort floor** (so workers don't over- or under-run)
- **Where to write output** and **what to return** (path + summary + confidence — *not* the full content)
- Verification commands / browser flows and success criteria
- **Stop conditions:** if code doesn't match, command fails after one retry, or needs out-of-scope files — stop and report

## Quality Gates

- No delegated patch accepted until it passes the verification its stakes demand
- Fable integrates and reviews the diff
- Treat subagent reports as **leads, not facts** — reopen cited files before relying on high-impact findings
- A `low`-confidence return or stopped-short slice is an escalation signal — bump effort or tier and re-run

## When NOT to Use This Skill

- **1 slice, or tightly coupled / interactive** → Fable does it directly at phase-appropriate effort
- **Ultracode is on** → Turn it off first; the two strategies conflict
- **The task needs the full Fable context** → Delegation overhead isn't worth it

## Classifier Blocks

If a Fable-served slice trips a safety classifier (cyber/bio-chem/distillation), bumping effort just re-blocks. On the Messages API the default is **BLOCK**, not auto-fallback.

**Fix:** Swap the model to Opus at the same effort. The fanout-template does this automatically.

---

## Credits

Adapted from BuilderIO's `efficient-fable` skill, extended with explicit model tiers, a conservative build-quality floor, the file-based context firewall, harness selection, and a budget-capped research workflow. This revision adds **effort-first routing**: a `low` default, per-phase orchestrator effort, and signal-driven (not predictive) escalation. It also adds a **hybrid routing** contract (static floor + logged raise-only override) and a **classifier-block** path (swap to Opus, don't bump effort), both grounded in the Fable 5 system card's fallback behavior. The orchestrator always verifies delegated work before relying on it — that review step is the point, not an afterthought.
