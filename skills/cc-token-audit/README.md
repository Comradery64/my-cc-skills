# cc-token-audit

A Claude Code skill that audits your **real** Claude Code token usage, finds where
your cost actually goes, recommends the context-saving tool that targets *your*
dominant cost bucket, and validates it with a **passive** A/B on your real work.

Everything runs on deterministic local tools (`ccusage`, `rtk`, the `claude plugin`
CLI) — **no API calls, $0 to run.**

## Why

Summing `usage` tokens × full API rates inflates the real bill 3–6× (mixed models,
subscription pricing, double-counted cache reads), and headless `claude -p` replays
are non-interactive, so they don't reflect how an end user drives Claude Code. This
skill anchors cost to `ccusage` ground truth, **excludes headless runs by default**,
and matches the tool to the cost structure instead of to marketing.

## Usage

```sh
# Phase 1+2 — baseline + tool-fit (free, instant)
python3 scripts/baseline.py --days 60

# inspect the excluded headless `claude -p` runs too
python3 scripts/baseline.py --days 60 --include-headless
```

`baseline.py` reports real spend (ccusage), token-volume shares, approximate
cost-share by bucket, top projects, the dominant bucket, a ranked tool
recommendation (across `context-mode`, `codegraph`, `ponytail`, `rtk`, and
`token-savior`), suggested tool **pairings** when the numbers justify a combo, and an
ROI check that ties the savings ceiling to your real annualized spend.

See [`SKILL.md`](SKILL.md) for the full method, guardrails, and the passive A/B
setup (Phase 3).

## Requirements

- [`ccusage`](https://github.com/ryoppippi/ccusage) (`npm i -g ccusage`, or falls back to `npx -y ccusage@latest`) — Node.js ≥18
- Python 3 (stdlib only)
- `claude` CLI with the `plugin` and `mcp` subcommands, plus `git` for Phase 3. Tool-specific installs (only for the one you A/B): Homebrew/cargo (`rtk`), npm/Node.js ≥18 (`codegraph`), python3/pip (`token-savior`)

## License

Apache-2.0 — Copyright 2026 Comradery64. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
