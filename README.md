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
