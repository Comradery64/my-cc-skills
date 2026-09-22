---
name: aws-compute-inventory
description: >-
  Inventory total vCPUs/CPUs and spend across ALL your AWS accounts, broken down
  by compute type (EC2, ECS-Fargate, EKS, RDS) and by account, plus a cost
  breakdown by account and service. Use this whenever someone asks how many
  CPUs/vCPUs/cores we have, how big our compute footprint is, what our fleet
  looks like across accounts, how much we're spending, our cost breakdown by
  account or service, or wants a capacity/cost audit — even if they don't say
  "vCPU" or name a specific account. Triggers on "how many CPUs do we have",
  "compute inventory", "cost breakdown", "spend by account", "what are we
  running across accounts".
---

# AWS multi-account compute + cost inventory

Answers "how much compute do we have, and what does it cost" across your whole
AWS Organization in one shot. It sweeps every account and region, counts vCPUs by
compute type, and pulls a cost breakdown from Cost Explorer.

## When to reach for this

Any question about fleet size, compute capacity, CPU/vCPU/core counts, or cloud
spend that spans more than one account. Examples: "how many vCPUs are we running
across all accounts", "what's our compute footprint", "break our AWS bill down by
account", "which account is costing the most", "give me a capacity audit". Don't
hand-roll `describe-instances` loops — this script already encodes the account
map, cross-account access, all-region sweep, and the cost-data gotchas.

## How to run it

One command produces the full report:

```bash
python3 scripts/inventory.py
```

Useful flags:
- `--no-cost` — skip the Cost Explorer query (vCPU inventory only, faster)
- `--json /tmp/inv.json` — also dump raw structured data for follow-up analysis
- `--months N` — months of cost history (default 3)

**Prerequisite:** a valid SSO session. The script reuses your AWS CLI profiles;
one login refreshes the shared SSO token for all of them:

```bash
aws sso login --profile mgmt-admin
```

If the run shows accounts under "Access errors", that's almost always an expired
session — re-login and rerun.

## What it does, and why it does it that way

The script (`scripts/inventory.py`) is the source of truth; this section explains
the reasoning so you can interpret results and extend it confidently. Each point
is a real footgun that produced wrong numbers before it was handled.

- **It sweeps ALL enabled regions, not just us-west-1/us-east-1.** SCPs never
  restrict the management account, and the Trainium account isn't region-confined
  either. A two-region scan missed management instances in us-west-2/us-east-2 and
  a Trainium `trn2` instance in **ap-southeast-4** (Melbourne). The script does a
  fast parallel EC2-count sweep to find active regions, then deep-scans those plus
  us-west-1/us-east-1 (where Fargate services and RDS live even when EC2 is absent).

- **EC2 vCPU = CoreCount × ThreadsPerCore** (from `CpuOptions`). Exact, no
  instance-type lookup needed.

- **ECS counts only FARGATE-launch tasks.** EC2-launch ECS tasks run *on* EC2
  instances already counted under EC2 — counting them again would double-count.
  Fargate vCPU = task `cpu` units ÷ 1024.

- **EKS nodes are NOT added separately.** Managed/self-managed node groups *are*
  EC2 instances (already in the EC2 total). Only Fargate pods would be additive,
  and pod vCPU needs the k8s API, so the script flags any EKS Fargate profiles for
  manual follow-up rather than guessing. (Today the org has no EKS at all.)

- **RDS vCPU comes from an EC2 instance-type lookup.** DB classes mirror EC2 types
  (`db.r6g.large` ↔ `r6g.large`). The field is `VCpuInfo.DefaultVCpus` — capital V
  **and** C. `DefaultVcpus` silently returns null.

- **Cost uses a `RECORD_TYPE=Usage` filter — this is essential.** the's accounts
  are fully covered by credits, so raw `UnblendedCost` nets to ~$0 (credits offset
  usage) and grouping by account shows every account at $0. Filtering to `Usage`
  strips credits/refunds/tax and reveals real spend. Without the filter the cost
  report is meaningless. Reported costs are therefore pre-credit, pre-tax usage —
  the "what we actually consumed" number, slightly below the gross invoice.

- **Trainium has no SSO profile** — the script assumes `OrganizationAccountAccessRole`
  into it from `mgmt-admin`.

- **Cost Explorer is queried from the payer (management) account** at the
  us-east-1 endpoint; LINKED_ACCOUNT grouping gives per-account spend.

## Output format

Markdown, with these sections (omit cost sections under `--no-cost`):

1. **vCPUs by compute type** — EC2 / ECS-Fargate / RDS / EKS + total
2. **vCPUs by account** — per-account columns for each type + totals
3. **Cost by account** — monthly usage charges, accounts sorted by spend
4. **Top services by cost** — latest full month, top ~12 services
5. **EKS Fargate follow-up** and **Access errors** — only if present

Always state that figures are **running resources, point-in-time** (stopped
instances are excluded) and that **EKS contributes 0** because its nodes are
counted under EC2. When presenting, lead with the headline total, then offer the
breakdowns. If an account shows under "Access errors," say so explicitly rather
than silently undercounting.

## Maintaining the account map

The account list lives at the top of `scripts/inventory.py` (`ACCOUNTS`). If the
org adds/removes an account or a profile name changes, update it there. An
unknown linked account ID appearing in the cost table (not in the map) just shows
its raw ID — add it to `ID_TO_LABEL` via the `ACCOUNTS` list if it becomes
relevant. Keep this in sync with wherever else your org documents its account map
(e.g. a root `CLAUDE.md` or internal wiki), if you maintain one.
