---
name: soc2
description: Review a project, PR, branch, diff, or the current session for SOC 2 Type 2 compliance. Use when asked to check SOC 2, audit readiness, or Trust Service Criteria coverage of code, infra, or CI changes.
argument-hint: [what to review] [--strict]
---

Run a SOC 2 Type 2 control review of: $ARGUMENTS

## 1. Scope

Review exactly what the argument describes (a PR, branch, commit range, unpushed or uncommitted work, a directory, or this session's changes). Gather it with `gh`/`git` as needed and state the scope in one line at the top of the report. No argument means the files touched in this conversation. `--strict` includes Low findings; default omits them.

Type 2 means controls must operate consistently over time, not just exist. When history is in scope, sample it: `git log --format='%h %an %s' -n 50`, merge-commit vs direct-push ratio, PR review and CI on every merge. For a PR, confirm review/approval/CI evidence exists on the PR itself. For work not yet pushed, review and CI have not happened, so do not report their absence; flag what would fail the gate once pushed (secrets in commits, unpinned actions, IAM widening) so it is fixed before it enters history.

## 2. Check controls

Work through `references/controls.md`. For each criterion, look for the listed evidence in the target. Skip criteria with nothing relevant in scope. Do not speculate about systems you cannot see; say "not in scope" instead.

Secrets rule: if a credential is found, report its location and type. Never print its value. Redact in any quoted line.

## 3. Report

Use this exact structure. No filler, no restating the checklist.

```
# SOC 2 Type 2 Review — <target>
Scope: <what was examined, one line>. Verdict: PASS | PASS WITH FINDINGS | FAIL

## Findings
| # | Sev | Criterion | Location | Issue | Fix |
|---|-----|-----------|----------|-------|-----|

## Controls Observed
- <criterion>: <control that is working, with evidence: file, PR approval, CI check>

## Not Assessable
- <criterion>: <what evidence would be needed and where it likely lives>

## Next Actions
1. <highest-severity fix, concrete, one line>
```

Severity: **Critical** = exposed secret, public data exposure, `*`/`*` IAM, auth bypass. **High** = no review/CI gate on protected branch, unencrypted sensitive data at rest or in transit, no audit logging on an access path, unpinned supply chain in prod deploy. **Medium** = missing MFA/session controls, broad but bounded permissions, no retention/backup evidence, missing dependency scanning. **Low** = documentation gaps, naming, minor hygiene.

Verdict: FAIL if any Critical, or any High that reaches production. PASS WITH FINDINGS otherwise if findings exist. Include only criteria where something was checked.

Location is `path:line` for code, PR number plus field for PR metadata, resource name for IaC. Every finding needs a fix that fits in one line. Cap Next Actions at 5, ranked by severity.
