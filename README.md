# Claude Code Skills Collection

A curated collection of reusable skills for Claude Code, focused on cost-efficient workflows, advanced patterns, and specialized capabilities.

## Available Skills

### [Frugal Fable](./skills/frugal-fable)

Run Fable (or any premium model) efficiently by combining two levers: **(1)** run at the lowest sufficient effort level and escalate only on signals, and **(2)** delegate heavy, verifiable work to cheaper models with a quality floor.

Perfect for token-heavy work: building features, multi-file changes, research, testing, debugging, migrations.

- **Key docs:** [README](./skills/frugal-fable/README.md) · [Full Guide](./skills/frugal-fable/SKILL.md)
- **References:** [Fan-out Template](./skills/frugal-fable/references/fanout-template.js) · [Routing Cheatsheet](./skills/frugal-fable/references/routing-cheatsheet.md)

### [cc-token-audit](./skills/cc-token-audit)

Audit your real Claude Code token usage, find where your costs actually go, and validate cost-saving recommendations with a passive A/B test on real work.

Runs on deterministic local tools with **$0 cost** — no API calls. Ground-truth spend via `ccusage`, excludes headless replays by default, and matches recommendations to your actual cost structure.

- **Quick start:** [README](./skills/cc-token-audit/README.md) · [Full Guide](./skills/cc-token-audit/SKILL.md)
- **Scripts:** [baseline.py](./skills/cc-token-audit/scripts/) — Phase 1+2 baseline + tool-fit analysis

### [gyb-archive-to-group](./skills/gyb-archive-to-group)

Offboard a Google Workspace user (or free up a shared mailbox address) by backing up their Gmail with GYB, renaming the account, creating a Google Group at the freed address, restoring the mail into the group's archive, then suspending the old account — without losing mail or paying for a dormant seat.

- **Quick start:** [README](./skills/gyb-archive-to-group/README.md) · [Full Guide](./skills/gyb-archive-to-group/SKILL.md)
- **References:** [First-time setup](./skills/gyb-archive-to-group/references/project-setup.md) · [Troubleshooting](./skills/gyb-archive-to-group/references/troubleshooting.md)
- **Scripts:** [verify_backup.sh](./skills/gyb-archive-to-group/scripts/verify_backup.sh) — reconciles a backup's on-disk files against its message DB

### [sso-dependency-audit](./skills/sso-dependency-audit)

Audits which third-party services are tied to a Google Workspace account's identity via SAML SSO or "Sign in with Google" OAuth, and checks whether each has a non-Google fallback login — before changing how that account authenticates (converting a shared mailbox to a Google Group, deprovisioning, enforcing a new IdP, killing a shared password, etc.). Strictly read-only — gathers evidence via GAM7, never mutates anything.

- **Full Guide:** [SKILL.md](./skills/sso-dependency-audit/SKILL.md)
- **Evals:** [evals.json](./skills/sso-dependency-audit/evals/evals.json)

### [gam-offboarding](./skills/gam-offboarding)

A hard-won runbook for offboarding an employee in Google Workspace via GAM7 — deprovision → remove group memberships → transfer Drive/Calendar data → wipe devices → suspend + archive → verify, in that order. Documents real gotchas measured against a live tenant: async device-wipe operations that report success before they've happened, AWS Identity Center sync quirks (group removal doesn't propagate but user suspension does), direct IAM account assignments that survive every other cleanup step, and more.

- **Full Guide:** [SKILL.md](./skills/gam-offboarding/SKILL.md)

### [aws-compute-inventory](./skills/aws-compute-inventory)

Inventory total vCPUs/CPUs and spend across every account in an AWS Organization in one shot — broken down by compute type (EC2, ECS-Fargate, EKS, RDS), by account, and by cost. Encodes real footguns: all-region sweeps (SCPs don't confine every account to your default regions), avoiding EC2/ECS double-counting, and a Cost Explorer filter that's the difference between real spend and "everything shows $0 because credits net it out."

- **Full Guide:** [SKILL.md](./skills/aws-compute-inventory/SKILL.md)
- **Script:** [inventory.py](./skills/aws-compute-inventory/scripts/inventory.py)

### [build-once-deploy-many](./skills/build-once-deploy-many)

Guides teams adopting a "build once, deploy many" CI/CD pattern — immutable, promotable artifacts instead of rebuilding per environment. Includes a full concrete implementation (Next.js + ECS Fargate + AWS: shared ECR, per-environment OIDC deploy roles, Secrets Manager wiring, Dockerfile gotchas) as a worked reference.

- **Full Guide:** [SKILL.md](./skills/build-once-deploy-many/SKILL.md)

### [daily-standup](./skills/daily-standup)

Generates concise standup summaries of work done in the last 24 hours (8pm cutoff) — pulls from git history and groups related commits into a coherent narrative instead of a raw commit-message dump.

- **Full Guide:** [SKILL.md](./skills/daily-standup/SKILL.md)
- **Scripts:** [generate_standup.py](./skills/daily-standup/scripts/generate_standup.py)

### [apartment-search](./skills/apartment-search)

Search for apartments matching your criteria — researches local market rates, scrapes live Craigslist listings, deep-dives promising ones, scores each for legitimacy/scam risk, and outputs a ranked table with confidence scores and key details.

- **Full Guide:** [SKILL.md](./skills/apartment-search/SKILL.md)

### [dev-browser](./skills/dev-browser)

Browser automation with persistent page state — navigate, fill forms, take screenshots, extract data, and test web apps across a multi-step session without losing context between steps.

- **Full Guide:** [SKILL.md](./skills/dev-browser/SKILL.md)

### [effective-engineering](./skills/effective-engineering)

A staff-level engineering copilot that prioritizes effectiveness (solving the right problems) over raw efficiency — questions assumptions, identifies root causes, and simplifies before writing code.

- **Full Guide:** [SKILL.md](./skills/effective-engineering/SKILL.md)

### [grill-me](./skills/grill-me)

Interviews you relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree — for stress-testing a design before committing to it.

- **Full Guide:** [SKILL.md](./skills/grill-me/SKILL.md)

### [mosyle-mdm](./skills/mosyle-mdm)

Mosyle Business MDM operations — Custom Commands, app deployment, device management, Installomator/Patchomator/Nudge — for managing a macOS fleet.

- **Full Guide:** [SKILL.md](./skills/mosyle-mdm/SKILL.md)

### [orchestrations](./skills/orchestrations)

A concise, cost-aware coordination policy for Codex/agentic work — when to fan out, when to run serially, and how to keep multi-agent work from burning budget for no reason.

- **Full Guide:** [SKILL.md](./skills/orchestrations/SKILL.md)

### [provision-k3s-github-runner](./skills/provision-k3s-github-runner)

Provisions a dedicated repo-level self-hosted GitHub Actions runner as a privileged docker-in-docker pod in a k3s cluster — for when a shared/org runner is inaccessible or unsuitable for a Docker build/push pipeline.

- **Full Guide:** [SKILL.md](./skills/provision-k3s-github-runner/SKILL.md)

### [task-manager](./skills/task-manager)

A CLI tool for managing on-disk Claude Code task lists outside of the built-in task tools — archiving, bulk cleanup, and dependency visualization.

- **Full Guide:** [SKILL.md](./skills/task-manager/SKILL.md)

### [soc2](./skills/soc2)

Reviews a project, PR, branch, diff, or the current session for SOC 2 Type 2 compliance — checks Trust Service Criteria (access, change management, availability, confidentiality, processing integrity) and reports findings by severity with concrete fixes. Includes an extended checklist section for AI-inference and GPU-control-plane workloads. Supersedes the older `/soc2` command below with a fuller control checklist and report rubric.

- **Quick start:** [README](./skills/soc2/README.md) · [Full Guide](./skills/soc2/SKILL.md)
- **References:** [controls.md](./skills/soc2/references/controls.md)

---

## Available Commands

Slash commands go in `commands/` — drop them into your Claude Code `commands` folder to use.

### [/brief](./commands/brief.md)
Reviews the conversation so far and produces a concise briefing: what was done, decisions made, and files changed.

### [/publish-check](./commands/publish-check.md)
A pre-publish readiness review for a tool — stops before any remote create/push/publish action to catch issues first.

### [/soc2](./commands/soc2.md)
Reviews the conversation and any files touched during the session, then produces a SOC 2–oriented compliance review.

---

## Using These Skills

1. Copy a skill directory into your Claude Code skills folder
2. Read the skill's README and SKILL.md to understand how and when to use it
3. Reference files in the `references/` directory for templates and quick lookups

Each skill is self-contained and can be used independently.

## Contributing

Have a skill you'd like to add? Open a PR with:
- A well-documented `SKILL.md` explaining the approach
- A `README.md` with quick start + examples
- Reference materials in `references/` if applicable
- Proper `.gitignore` to keep repos clean

---

Made for the Claude Code community.
