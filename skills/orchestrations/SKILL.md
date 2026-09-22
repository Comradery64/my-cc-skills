---
name: orchestration
description: Concise, cost-aware coordination policy for Codex work.
---

# Orchestration policy

Prefer the smallest safe execution path and make progress visible.

## Routing

- Single-chain tasks: work directly in root context.
- Delegate one self-contained worker only when it materially saves time or adds
  independent verification; at most two genuinely independent read-only scouts.
- Use `fork_turns=none` unless the user explicitly requests context inheritance.
  Worker reports are <=200 words and contain paths/evidence, not transcripts.
- User-named cost-control skills override generic orchestration guidance.
- Avoid unbounded parallelism, trivial delegation, maximal questioning, inherited
  full histories, and unattended workers as defaults.

## Visibility and scope

- Announce every new phase before tools; update the user at least every 60s.
- Never continue background work after sending a final response.
- If the user expresses surprise or asks what is running, pause/interrupt workers
  and report state before proceeding.
- Adjacent post-completion deliverables are new scope; state a cost band first.

## GitHub identity

- The default GitHub account is `Comradery64`.
- Use `RadixAlan` only when the user explicitly requests it for the current operation.
- After that operation, restore `Comradery64`; never treat `RadixAlan` as persistent.
- Verify the active account before any GitHub mutation.

## Bounded review

Default to one independent review and one targeted remediation. Run narrow tests
once and the full suite once after final changes. Further cycles require new
evidence and a user-visible explanation.

## Context and cost checkpoints

Use [context-handoff](../../../.codex/skills/context-handoff/SKILL.md) at meaningful
boundaries to maintain verified state and assess fresh-session value. Latest-request
input is context pressure; root-plus-worker cumulative usage is a separate cost
ledger. There is no default cumulative-token approval gate. Explicit user budgets
still apply. Unknown usage is not zero and does not independently block work.

## Ledger guard

Run `scripts/token_budget_guard.py --session <exact-id-or-path> --tree --json` when
a cost report is useful. It uses CODEX_THREAD_ID only if the session is omitted;
never chooses the newest unrelated chat. Exit 0 reports observed usage, 30 unknown.
Optional explicit thresholds retain advisory/budget exits 10/20; no defaults apply.
The CLI delegates to the shared context-handoff ledger. Do not scan all logs per tool.

## Signature rule

Every delegated task states scope, read-only status, expected output, and stop
condition. Keep coordination proportional to the task.
