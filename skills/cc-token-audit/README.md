# cc-token-audit

Audit your real Claude Code token usage, find where costs actually go, get tool recommendations matched to your cost structure, and validate with a passive A/B test.

Runs locally with **$0 cost** — no API calls, deterministic tools only (`ccusage`, `claude` CLI, Python 3).

**Quick start:**
```sh
python3 scripts/baseline.py --days 60
```

Reports real spend, token-volume shares, cost breakdown by bucket, top projects, and ranked tool recommendations. See [SKILL.md](SKILL.md) for the full method and passive A/B setup.

**Requirements:** `ccusage` (Node.js ≥18), Python 3, `claude` CLI.
