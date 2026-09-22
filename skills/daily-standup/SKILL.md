---
name: daily-standup
description: Use when generating concise standup summaries of work done in the last 24 hours (8pm cutoff)
---

# Daily Standup

## Overview

Generate a synthesized standup report from git activity across all projects in `~/Dev/Work`.

**How it works:** The skill runs `index.sh [date]`, which emits rich raw material (full commit subjects, bodies, PR references, WIP status). Claude — not the script — reads that output and synthesizes it into human-readable bullets. The script's job is to provide complete, specific detail; Claude's job is to distill it.

Uses an **8pm (20:00) cutoff** — work after 8pm counts toward the next day, grouping effort naturally by workday.

## When to Use

- Daily standup preparation
- Work summary for status updates
- Retrospective on activity by date

## Quick Usage

```bash
/daily-standup              # Last 24 hours (8pm yesterday to 8pm today)
/daily-standup 2026-06-12   # Specific date (8pm that day to 8pm next day)
```

## 8pm Cutoff

- **No argument:** window = yesterday 20:00 → today 20:00
- **With date:** window = that date 20:00 → next date 20:00
- **Reason:** Groups work naturally by workday; late-night commits appear in the next standup

## Synthesis Rules

### Git sections — group by project/domain

For each active repo (one that has commits in the window):

1. **Synthesize, don't enumerate.** Never list raw commit subjects one-by-one. Find the arc — what problem was being solved, what was shipped, what was unblocked.
2. **3–4 bullet points per project.** Lead with business/technical impact, not file names.
3. **Include PR numbers and merge status.** e.g. "merged via PR #382", "keel#382 cross-ref".
4. **Be specific.** Name the actual resource, permission, or service — not "IAM and S3 policy updates".
5. **Include WHY.** Enables X / unblocks Y / fixes production bug Z.

### IT Manager / Ops (Bee) section — synthesize separately

If the raw output contains a `## IT Manager / Ops (Bee)` section, synthesize it **separately** under its own heading using these buckets:

- **People / Decisions** — approvals, sign-offs, personnel actions
- **Unblocks** — blockers cleared, dependencies resolved
- **Ops** — tickets, escalations, vendor comms, scheduling

Do NOT force meeting notes or ops activity into git repo buckets. Keep the two domains distinct.

**Graceful degradation:** If there is no Bee section in the raw output, produce only the git standup. Never mention the Bee section or its absence.

## Common Mistakes

- **Over-detailing:** Listing all commits/files → destroys conciseness. Synthesize impact.
- **Vague:** "Fixed things" → "Fixed deploy role permissions: ec2:ModifySecurityGroupRules, Loki read access"
- **Missing PRs:** Always include PR #s and merge status when present in commits
- **No context:** Always explain WHY (enables feature X, unblocks team Y, fixes production bug Z)
- **Listing vs. synthesizing:** "feat: add X, fix: add Y" → group related work, explain the arc

## Real-World Format

✅ Good:
```
**company-infra: EC2 Benchmark Stack + Deploy Permissions & CI Workflow**
- Added dev EC2 benchmark stack (c7i.4xlarge, us-west-2); fixed SCP exemptions + deploy role IAM for RunInstances
- Fixed deploy role permissions: ec2:ModifySecurityGroupRules, Loki secret read + GetResourcePolicy
- Scoped manual Terraform dispatch to selected stacks; wired rx-creds secret into harness sidecar (keel#382 integration)
- 13 commits merged across 4 PRs; platform-organization SCP apply must precede ec2-benchmark-1
```

❌ Bad:
```
- Modified main.tf in benchmark-config-store
- Modified variables.tf in benchmark-config-store
- Updated iam.tf in ec2-benchmark-1
- IAM and S3 policy updates
```

## Archive Instruction

After producing the final synthesized report, write it to:

```
~/Dev/Work/Daily_Standup/standup-<END-DATE>.md
```

Use the END date (YYYY-MM-DD) from the window as the filename date. Create the directory if it does not exist (`mkdir -p`). This builds a retro log for future reference.

Example: for the default no-arg run on 2026-06-16, the END date is 2026-06-16, so the file is `standup-2026-06-16.md`.
