---
name: frugal-fable
description: Use when running on Claude Fable (or any premium model) and the work is token-heavy — building features, multi-file changes, research, testing, debugging, migrations, or anything spanning many files/sources. Two levers, applied in order: (1) run Fable at the LOWEST effort that clears the bar and escalate only on a signal, and (2) delegate bounded, verifiable heavy-lifting to cheaper models — with a quality floor so construction is never owned by a weak agent. Triggers on requests to "be efficient with Fable", "don't burn tokens", orchestrate subagents, or delegate work.
---

# Frugal Fable

Fable is expensive because Fable is good. There are two ways to overspend on it:
running it harder than the task needs, and making it personally do work a cheaper
agent could do. This skill attacks both, **in that order** — effort first,
delegation second — because effort is the primary cost dial and it applies to the
orchestrator tokens you can't delegate away.

**The deal:** run Fable at the lowest effort that clears the bar; escalate only
when a concrete signal says you undershot. Cheaper agents *gather signal and
produce candidate work to files*. Fable *decides, integrates, and reviews*.
Truth-judgment and final quality stay with Fable, always.

## ⚠️ Turn Ultracode OFF before using this skill

frugal-fable and **Ultracode are opposites** and must not run together.
Ultracode's standing order is *"run a workflow for every task, token cost is not
a constraint, be exhaustive, loop until nothing is left."* frugal-fable's whole
purpose is to **conserve**. Run both and cheap workers fan out *and then* Fable
launches exhaustive passes on top — exactly how usage gets blown.

- If Ultracode is on, **say so and stop** — ask the user to toggle it off via the model selector, then proceed.
- This skill is a *guide*, not a hard cap. The only thing that truly enforces a ceiling is a **token budget in the workflow** (see Budget discipline). Use it.
- After a delegated workflow returns, **do NOT autonomously launch a second "gap-fill" round.** Read the saved files, synthesize, and stop. Widen scope only if the user asks.

## Lever 1 — Effort first (the dial that's always on)

Effort is the primary control over the intelligence/latency/cost trade-off, and
unlike delegation it applies to the orchestrator's own tokens — the decompose,
integrate, and review passes that by design never leave Fable. Getting effort
wrong here is pure waste with nothing to delegate it to.

**Default everything to `low`.** Lower-effort Fable still performs well and often
exceeds high-effort prior models. Start there and let signals pull you up; do not
start high "to be safe" — that is the single fastest way to burn the limit.

> **⚠ Caveat — how flat the effort curve is depends on the task family.** The
> "low often clears the bar" claim is strongest on SWE-bench-shaped work, where
> the published cost/effort curve is nearly flat (low captures ~90%+ of the
> achievable quality — see the Fable 5 system card, Fig 8.2.A). It is *weakest*
> on hard, novel agentic-repo work — subtle multi-file refactors, correctness-
> and security-critical changes, from-scratch reconstruction — where the curve is
> steep (on FrontierCode Diamond, Fig 8.4.A, low captures only ~1/3 of the
> achievable quality). On those slice types, `low` may leave most of the model's
> capability on the floor, and the escalation net below is least reliable there
> (a low-effort agent can scope-creep or mislabel a bug as a "convention" and
> still return `confidence: high`, passing a shallow verify). This does **not**
> change the default — still start `low` and react — but treat a `low` start on a
> steep-curve slice as a *known gamble*: instrument it (Memory), lean on the
> adversarial verifier, and don't be surprised when these are the slices that
> escalate. When a slice is *obviously* one of these and you have a prior that it
> needs more, that's exactly what a logged upward override is for (see Routing).

*Provenance note:* the flat-curve evidence is measured on **Mythos 5** (the
unsafeguarded sibling), not Fable, and on Fable the card only characterizes
medium-and-up. So "low is nearly free" is an inherited assumption for Fable, not
a measured one — another reason to instrument rather than trust it blindly.

### You can't predict effort upfront — so don't. React instead.

The trap is thinking you must know a slice's difficulty before you touch it. You
don't. You need a cheap way to *detect you undershot and correct*, which is a far
easier problem. Three rules resolve the catch-22:

1. **Decomposition prices the slices.** The act of decomposing already produces
   the information — score each slice on stakes / reversibility / ambiguity (you
   score these for model tier anyway) and read an **effort floor** off the same
   scores. High-ambiguity or high-stakes slice → higher floor. This isn't
   prediction; it's reading effort off a judgment you're already making.

2. **The orchestrator's own effort follows the phase, not the session.** The
   three things Fable never delegates want different effort:
   - **Decompose** a fuzzy problem → `high` (this is where judgment compounds).
   - **Integrate** clean, pre-verified patches → `low` (mechanical).
   - **Final review** → scale to the stakes of what's shipping.
   Phase is always knowable at the moment you enter it, so this is never a guess.

3. **Escalate on a signal, never on a hunch.** Re-run a slice at higher effort
   only when something concrete fires: a failed verification gate, a `low`
   confidence return, a subagent that stopped short, or a review that finds the
   output doesn't match the spec. A targeted re-run on the one slice that needed
   it is far cheaper than running everything high on the chance that one might.
   Anthropic's own rule, inverted: *reduce effort when a task completes but takes
   longer than needed* — so default low and let failure, not fear, raise it.

**A classifier block is NOT a quality signal — don't bump it, swap the model.**
Fable ships with safety classifiers (cyber, bio/chem, distillation) that can fire
mid-run. On the **Messages API the default is to BLOCK** — a structured refusal,
*not* an automatic Opus fallback (that's a client-app behavior; server-side
fallback is opt-in). Two consequences for this skill:
- If a delegated slice is served by **Fable** and trips a classifier, raising its
  *effort* does nothing — it just re-blocks. The fix is a **model swap** to a
  non-Fable model (Opus) at the *same* effort. The fan-out template does this
  automatically (`isClassifierBlock` → retry on Opus, once) and tags it
  `swappedToOpus`; if Opus is also blocked or the retry fails, the slice lands in
  `needsFable` with no result rather than being silently dropped.
- This mostly matters for the **orchestrator itself** and any slice you route to
  Fable. If you're an infra/security-adjacent shop, your legitimate work is more
  likely than average to trip the cyber classifier, and the card publishes **no
  false-positive rate** for benign coding — so treat spurious blocks as an
  expected operational event, not an edge case. Watch for them; if they're
  frequent on real work, that's a signal to move the affected task types onto Opus
  by default (via a logged override) rather than fighting the classifier.

**First encounter vs. repeat.** Genuinely novel work can't be priced in advance
by anyone. That's not a reason to run high — it's a reason to **instrument**: note
via `/usage` which slices blew past expectation and record it (see Memory). The
second build of a familiar shape *is* predictable because you have a prior. The
catch-22 is real only on first contact and decays with every repeat.

## Lever 2 — Delegation (route heavy, verifiable work down)

Once effort is set, keep Fable off work a cheaper agent can do to a passing bar.

### What stays with Fable (never delegated)

- Decomposing ambiguous work into clean, independent slices.
- Architecture, product, and safety tradeoffs.
- Shared-file coordination and integrating partial work into one coherent whole.
- Resolving conflicting subagent reports — deciding what's actually true.
- Final review, risk assessment, and user-facing synthesis.

### Model + effort routing — static floor, logged upward override (hybrid)

The routing table below is the **static default policy** — the floor. It is not a
per-task free choice: you don't get to talk yourself into a cheaper tier at
runtime. What you *may* do is override a slice **upward** when you have a concrete
reason, and when you do, **log the reason** so the deviation is auditable after
the run. This is the deal: the table decides by default; Fable can raise, never
lower, and every raise carries a justification.

Why this shape rather than "Fable decides everything at runtime": the failure
modes documented for this model family — overconfidence, scope creep, stopping
early while silently blaming token budget — are exactly the ones that corrupt a
free-runtime routing call ("this looks easy, I'll send it low"). Pinning the
floor in a static table you own, and forcing overrides to be raise-only and
logged, keeps the model's known weak spot out of the cost-control loop while
still letting real judgment raise the bar. The `fanout-template.js` enforces this
mechanically: `resolveLevel()` clamps any downward override back to the floor and
logs it; upward overrides without a `reason` get a ⚠ in the log.

Score each slice on three axes; the highest one sets both the **model floor** and
the **effort floor**:

- **Stakes** — ships to prod? architectural? security/correctness-critical? → raises floor
- **Reversibility** — one-way door, hard to test, destructive? → raises floor
- **Ambiguity** — spec fuzzy, needs real judgment? → raises floor, often stays with Fable

| Slice | Owner | Effort floor | Gate before Fable accepts |
|---|---|---|---|
| Scans, grep, repo/web inventory, log & test-output reduction, doc summaries | **Haiku** | low | low-stakes; sanity-check only |
| Bounded, well-specified patches; adversarial verification; targeted tests | **Sonnet** | low–medium | build + relevant tests pass |
| Hard refactors, correctness/security-critical code, slices where Sonnet visibly struggles | **Opus** | medium | Fable reviews the diff |
| Decompose / architect / coordinate / final review | **Fable** | per phase (see Lever 1) | — |

**Overriding upward (the logged escape hatch).** In the fan-out template, attach
an `override` to a slice: `override: { tier: 'opus', reason: '...' }`. It's
clamped raise-only against the table and logged. Use it when you have a *prior*
that the floor will undershoot — most often a steep-curve slice (see the effort
caveat in Lever 1) or a shape your Memory notes flag as an escalator. This is how
the hybrid stays honest: the exception is expressible, but it's on the record.

**Conservative build floor (this project's default):** cheap models do mechanical
work and bounded patches that come with passing tests. Anything architectural,
high-stakes, or one-way stays with **Opus or Fable**. When unsure which tier or
effort, go **up one** — a re-run that wasn't good enough costs more than starting
at the right level.

## Budget discipline (the real brake)

A skill convention biases behavior; it cannot force a spend limit. When the user
is on a constrained usage window — or you're running unsupervised — use a
workflow with a **hard token cap**, not just routing advice:

- For research, use the bundled **`references/frugal-research.js`** (hard caps: 4 angles / 8 fetches / 10 claims / 2 votes, a `budget.remaining()` gate that stops fanning out, synthesis pinned to Sonnet). Run via the `Workflow` tool with `{scriptPath: "<abs path>"}`, or copy to `~/.claude/workflows/`.
- In any custom `Workflow`, gate fan-out on `budget.remaining()` and keep a reserve for synthesis. See `references/fanout-template.js`.
- **Scope is a cost lever.** A 6-lane, 12-question mega-prompt makes even "cheap" workflows expensive (verify fans out per claim). Split huge asks into focused runs, or cap the angles. Tell the user the tradeoff instead of silently fanning out to 100 agents.
- **"Cheap model" ≠ "cheap run."** 75 Sonnet agents at ~27k each is still ~2M tokens. Watch the *count*, not just the per-agent tier.
- **Effort is a budget lever too.** A fan-out of low-effort Sonnet agents costs a fraction of the same fan-out run high. Set the effort floor on delegated slices, not just the model.

## The context firewall (the main token saver)

The thing that nukes Fable's budget is subagent output landing *in Fable's
context*. So don't return it there.

- Delegated agents **write findings/patches/logs to a scratch dir**
  (`.frugal-fable/<task>/` in the repo, gitignored) and **return only**:
  `path` + a 3-line summary + a confidence level.
- Fable reads a file **on demand** — only the ones that matter, only at the moment
  it needs them (usually synthesis/review). Not all of them, not up front.
- For research, prefer tools that already write to file over ones that dump into
  context (the Bright Data skills do this — see Lanes).

This keeps Fable's working set small even across dozens of subagents.

## Planning tasks: the routing plan IS part of the deliverable

When the task itself is to *plan* multi-phase work (a project plan, roadmap,
phased build-out), the routing this skill produces at runtime — per-slice
owner model, effort floor, parallel/series schedule, verification gate,
escalation triggers, and pre-flagged ▲ upward overrides for steep-curve
slices — must be **written into the deliverable** (an `ORCHESTRATION.md`
next to the plan, or a routing section per phase), not just applied silently
in-session. Two reasons: the next session inherits priors instead of
re-deriving them, and the user can audit the spend plan before it runs.

Also: if reconnaissance shows the project family already keeps orchestration
docs as repo artifacts, that is a convention to follow, not optional color —
"how the team worked" docs are in scope for a planning deliverable.

*Origin (2026-08-31, BeatSaber98):* the skill was applied correctly at
runtime but the shipped plan had no routing map; the user had to ask for it
separately, even though all three sibling repos carried ORCHESTRATION docs
the recon had surfaced.

## Handoff packets

Write every delegated prompt as if the agent has zero chat context. Include only:

- Exact objective + the repo path.
- In-scope files/surfaces, and what's explicitly **out of scope**.
- The slice's **effort floor** (so the worker doesn't over- or under-run).
- **Where to write output** (the scratch path) and **what to return** (path + summary + confidence — *not* the full content).
- Verification commands / browser flows to run, and what success looks like.
- **Stop conditions:** if code doesn't match the prompt, a command fails after one retry, or the task needs out-of-scope files — stop and report, don't improvise.

## Give the reason, not only the request

Fable gets things right the first time more often when it understands intent —
which means fewer correction rounds and fewer escalations. For every non-trivial
delegation and for the top-level task, state *why*: what larger goal this serves,
who it's for, what the output enables. A slice that lands first-try at low effort
never triggers the escalation that would have cost you.

## Construct a memory system

Record what each task type actually cost so the next run isn't a guess. This is
what turns the "you can't predict effort" problem from permanent into first-time-only.

- Store one lesson per file with a one-line summary at the top.
- Record which slice shapes needed escalation and why, and which ran fine at `low`.
- Don't save what the repo or chat already records; update an existing note rather than duplicating; delete notes that turn out wrong.

## Choosing the harness — not every task needs a workflow

- **1 slice, or tightly coupled / interactive** → Fable does it directly at the phase-appropriate effort. No delegation; coordination cost would exceed savings.
- **A few independent slices** → inline `Agent` calls (set model *and* effort per the table).
- **Many independent slices / heavy fan-out** → author a `Workflow` (agents run *outside* Fable's context — cheapest). Adapt `references/fanout-template.js`.
- **Research** → `frugal-research` (hard budget cap) when usage is constrained or unsupervised; `deep-research-cheap` when you have headroom. Don't rebuild either.

## Lanes (soft defaults, not rigid rules)

- **Build/execute:** Fable plans + owns shared files, integration, and final review, at phase-appropriate effort. Cheaper agents produce *candidate* bounded patches to the scratch dir with passing tests. **Quality gate:** no patch accepted until it passes the verification its stakes demand. Fable integrates and reviews — never rubber-stamps a delegated diff.
- **Research:** delegate to `deep-research-cheap` (Haiku collects via `bdata` + WebSearch, Sonnet verifies adversarially, Fable synthesizes). For one-off lookups, a single Haiku agent writing to a scratch file. Prefer `bdata` over built-in web tools.
- **Testing:** Fable names the validation direction and which checks matter. Lighter agents run targeted tests, browser flows, screenshots, log reduction; report exact commands, failures, likely cause, and whether failures look real / flaky / environmental.
- **Debugging:** cheaper agents cluster logs, reproduce, try small fixes; Fable decides which diagnosis is trustworthy and owns the real fix.

If a task is tiny, or the validation itself needs delicate judgment, keep it with Fable.

## Vetting delegated work

Treat subagent reports as **leads, not facts**. Before relying on a high-impact
finding, opening a PR, or telling the user it's done: reopen the cited file(s),
confirm the line refs / failures, and review the final diff against the task. A
`low`-confidence return or a stopped-short slice is an escalation signal — bump
effort or tier and re-run that slice, don't paper over it.

## References

- `references/frugal-research.js` — budget-capped research `Workflow` (Haiku collect → Sonnet verify → Sonnet synthesize, hard caps + token gate).
- `references/fanout-template.js` — adaptable `Workflow` for the general fan-out case: static routing floor + logged raise-only override, per-slice model *and* effort, adversarial verify, signal-driven quality escalation, and a classifier-block → Opus-swap path (blocks are not quality failures). Copy and adapt; don't run blind.
- `references/routing-cheatsheet.md` — one-screen routing table + effort ladder + firewall protocol for quick recall mid-task.

