#!/usr/bin/env python3
"""cc-token-audit — Phase 1+2: baseline + tool-fit, from REAL Claude Code usage.

$0: reads ccusage (local, parses CC logs; NO API calls). Ground truth = ccusage's
own cost. We report token-VOLUME shares (model-independent, honest) plus an
approximate rate-weighted cost-share, and map the dominant cost bucket to the tool
most likely to help. We do NOT estimate $ by tokens*full-rate (that inflates 3-6x).

Headless `claude -p` runs are EXCLUDED by default: they file under "Unknown Project"
(no resolvable cwd) and are non-interactive, so they don't reflect an end user's
interactive cost and aren't used for the recommendation. Use --include-headless to
include them.

Usage: baseline.py [--days 60] [--include-headless]
"""
import json, subprocess, sys, argparse, datetime as dt, collections, shutil

# Anthropic per-token cost RATIOS relative to fresh input=1 (used only for
# approximate cost-SHARE; absolute $ comes from ccusage):
RATIO = {"input": 1.0, "output": 5.0, "cache_create": 1.25, "cache_read": 0.1}

# ccusage labels for sessions with no resolvable project cwd — this is where
# headless `claude -p` runs land. Treated as non-representative by default.
HEADLESS_LABELS = {"Unknown Project", "", "?"}

def runner():
    if shutil.which("ccusage"): return ["ccusage"]
    if shutil.which("npx"): return ["npx", "-y", "ccusage@latest"]
    sys.exit("ccusage not found. Install: npm i -g ccusage  (or use npx).")

def ccu(args):
    out = subprocess.check_output(runner() + args, text=True)
    return json.loads(out)

def is_headless(s):
    # Headless `claude -p` runs don't register a resolvable project cwd, so
    # ccusage files them under "Unknown Project" (or a blank path). They're
    # non-interactive, so they're excluded from the recommendation by default.
    return (s.get("projectPath") or "").strip() in HEADLESS_LABELS

def agg(sessions):
    tot = collections.Counter(); cost = 0.0
    keymap = {"inputTokens": "input", "outputTokens": "output",
              "cacheCreationTokens": "cache_create", "cacheReadTokens": "cache_read"}
    for s in sessions:
        for src, dst in keymap.items(): tot[dst] += s.get(src, 0) or 0
        cost += s.get("totalCost", 0) or 0
    return tot, cost

def agg_daily(daily_rows):
    """Aggregate `ccusage daily --json` rows (each row has modelBreakdowns[]) into
    the same (Counter, cost) shape as agg(). Used when `ccusage session` returns 0
    — e.g. when CLAUDE_CONFIG_DIR redirects the config dir, or transcripts are a
    format `session` won't parse, but `daily` still sees the data."""
    tot = collections.Counter(); cost = 0.0
    keymap = {"inputTokens": "input", "outputTokens": "output",
              "cacheCreationTokens": "cache_create", "cacheReadTokens": "cache_read"}
    for r in daily_rows:
        for m in r.get("modelBreakdowns", []):
            for src, dst in keymap.items():
                tot[dst] += m.get(src, 0) or 0
            cost += m.get("cost", 0) or 0
    return tot, cost

def installed_tools():
    """Best-effort detection of which context-savers are already installed, so the
    recommendation reads 'you already have it — the lever is usage' instead of
    'install it'. (claude plugin/mcp list make no model calls → stays free.)"""
    out = ""
    for cmd in (["claude", "plugin", "list"], ["claude", "mcp", "list"]):
        try:
            out += subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.lower()
        except Exception:
            pass
    have = {"context-mode": "context-mode" in out,
            "codebase-memory-mcp": "codebase-memory-mcp" in out or shutil.which("codebase-memory-mcp") is not None,
            "token-savior": "token-savior" in out,
            "ponytail": "ponytail" in out,
            "cozempic": "cozempic" in out or shutil.which("cozempic") is not None}
    have["rtk"] = shutil.which("rtk") is not None
    return have

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--include-headless", action="store_true",
                    help="include headless `claude -p` ('Unknown Project') runs "
                         "(default: excluded as non-representative)")
    ap.add_argument("--until", metavar="YYYY-MM-DD",
                    help="end the window on this date (inclusive) instead of today, "
                         "e.g. to baseline the 60 days BEFORE a spend incident")
    a = ap.parse_args()
    end = dt.date.fromisoformat(a.until) if a.until else dt.date.today()
    since = end - dt.timedelta(days=a.days)
    since_s, end_s = since.isoformat(), end.isoformat()

    # Source the cost shape from the SESSION view so headless runs can be split out.
    sessions = ccu(["session", "--json"]).get("sessions", [])
    fallback = False
    if sessions:
        def in_win(s):
            day = (s.get("lastActivity") or "")[:10]
            if not day:
                return a.until is None  # keep undated sessions only in default (today) mode
            return since_s <= day <= end_s
        win = [s for s in sessions if in_win(s)]
        headless = [s for s in win if is_headless(s)]
        analyzed = win if a.include_headless else [s for s in win if not is_headless(s)]
        tot, cost = agg(analyzed)
        _, headless_cost = agg(headless)
    else:
        # FALLBACK: `ccusage session` returns [] on some setups (CLAUDE_CONFIG_DIR
        # redirect, non-standard transcript formats) even when `daily` sees the
        # data. Aggregate daily directly — loses per-project + headless split, keeps
        # the cost-bucket analysis that drives the recommendation.
        fallback = True
        daily = ccu(["daily", "--json", "--since", since_s, "--until", end_s]).get("daily", [])
        tot, cost = agg_daily(daily)
        headless_cost = 0.0
        analyzed = []  # no session rows; have_data below gates the empty case
    total_tok = sum(tot.values()) or 1
    have_data = sum(tot.values()) > 0 or cost > 0

    win_desc = f"since {since_s}" if a.until is None else f"{since_s} .. {end_s}"
    print(f"\n{'='*64}\n  CLAUDE CODE USAGE AUDIT — {a.days}-day window ({win_desc})\n{'='*64}")
    if fallback:
        print(f"  Spend (ccusage daily, fallback): ${cost:,.2f}   over the {a.days}-day window")
    elif headless and not a.include_headless:
        raw = cost + headless_cost
        share = headless_cost / (raw or 1) * 100
        print(f"  Apparent spend (all sessions):  ${raw:,.2f}")
        print(f"  Excluded (headless `claude -p`): ${headless_cost:,.2f}  ({share:.0f}% — 'Unknown Project', non-interactive)")
        print(f"  Real interactive spend:         ${cost:,.2f}   over {len(analyzed)} sessions")
        if share >= 20:
            print(f"  Note: headless runs are {share:.0f}% of the apparent bill. They're non-interactive,")
            print(f"        so they're excluded from the recommendation by default.")
            print(f"        Re-run with --include-headless to include them.")
    else:
        label = "Real spend (ccusage)" if not a.include_headless else "Spend incl. headless"
        print(f"  {label}:     ${cost:,.2f}   over {len(analyzed)} sessions")
    print(f"  Total tokens:             {total_tok/1e6:,.1f}M")
    if fallback:
        print(f"  (Fallback: `ccusage session` returned 0 — common when CLAUDE_CONFIG_DIR redirects")
        print(f"   the config dir or transcripts are non-standard. Per-project + headless split unavailable.)")
    print()

    if not have_data:
        print("  No sessions in window — nothing to recommend.")
        print("  If spend looks wrong (0 everywhere): the user likely runs a redirected config")
        print("  (CLAUDE_CONFIG_DIR) — set it before running, or check whether `ccusage daily` sees data.")
        if not fallback:
            print("  (Otherwise all sessions in this window were headless `claude -p` — re-run with")
            print("   --include-headless to include them.)")
        print()
        return

    print("  Token VOLUME share (model-independent):")
    for k in ("cache_read", "cache_create", "output", "input"):
        print(f"    {k:14} {tot[k]/1e6:9.1f}M   {tot[k]/total_tok*100:5.1f}%")
    weighted = {k: tot[k]*RATIO[k] for k in tot}
    wsum = sum(weighted.values()) or 1
    print("\n  Approx COST share (rate-weighted; absolute $ above is ccusage truth):")
    for k in ("cache_read", "cache_create", "output", "input"):
        print(f"    {k:14} ~{weighted[k]/wsum*100:5.1f}% of cost")
    print("    (rate-weighted with Claude pricing — indicative for non-Claude/proxied models;")
    print("     the absolute $ above is ccusage's truth, not this share.)")

    cache_share = (weighted["cache_read"]+weighted["cache_create"])/wsum
    out_share = weighted["output"]/wsum
    in_share = weighted["input"]/wsum
    print(f"\n  => context/cache = ~{cache_share*100:.0f}% of cost | output = ~{out_share*100:.0f}% | fresh input = ~{in_share*100:.1f}%")
    # Dominant-bucket trigger: cache is "dominant" if it's the largest COST bucket
    # (plurality) OR ≥70% of token VOLUME. The volume backstop catches cases where
    # a cheap-cache non-Claude/proxied model makes cache's COST share look modest
    # (e.g. 54%) even though 94% of every token the model reads is cache_read.
    cache_vol_share = (tot["cache_read"] + tot["cache_create"]) / total_tok
    cache_dominates = (cache_share > out_share and cache_share > in_share) or cache_vol_share >= 0.70

    # per-project (real interactive only)
    byproj = collections.defaultdict(lambda: [0, 0.0, 0])
    for s in analyzed:
        p = (s.get("projectPath") or "?").rstrip("/").split("/")[-1] or "?"
        byproj[p][0] += 1; byproj[p][1] += s.get("totalCost", 0) or 0; byproj[p][2] += s.get("cacheReadTokens", 0) or 0
    if byproj:
        print(f"\n  Top projects by cost (real interactive, last {a.days}d):")
        for p, (n, c, cr) in sorted(byproj.items(), key=lambda x: -x[1][1])[:10]:
            print(f"    ${c:8.2f}  {n:3d} sess  cacheRead {cr/1e6:7.0f}M  {p}")

    # recommendation (computed on REAL interactive usage). Five tools, each aimed
    # at a specific bucket; the ranking floats context-mode to #1 when cache/context
    # dominates (the usual case), then lists the others in fit order.
    print(f"\n{'─'*64}\n  TOOL-FIT (which context-saver targets YOUR dominant cost):\n{'─'*64}")
    have = installed_tools()
    recs = []
    if cache_dominates:
        recs.append(("context-mode", f"~{cache_share*100:.0f}% of your cost is context/cache. IMPORTANT: context-mode INDEXES tool outputs for recall (ctx_search) + auto-redirects curl/wget to a sandbox — it does NOT auto-compress current context (Read/Bash pass through with advisory tips). It only cuts cache_read when the agent USES its ctx_* tools at the source (ctx_execute_file over Read, ctx_batch_execute over N command runs). Don't expect it to halve cache_read alone — it caps marginal growth when used; pair with codebase-memory-mcp."))
        recs.append(("codebase-memory-mcp", f"a code-intelligence MCP: indexes the repo into a persistent tree-sitter knowledge graph (158 langs + Hybrid LSP for Rust/TS/Python/Go/…), sub-ms structural queries, cross-repo edges. One graph query replaces dozens of grep/Read cycles (its bench: ~99% fewer tokens on structural queries). Attacks the SAME context/cache bucket from the input side; strongest when fresh-input share is high (yours ~{in_share*100:.0f}%) and the repo is big. Pairs with context-mode."))
        recs.append(("cozempic", f"ESCALATION if the read-only tools above don't move the needle: cozempic ACTIVELY PRUNES the live transcript (18 strategies — trims stale reads, old tool results by age, thinking blocks, duplicate reminders, >8KB tool outputs) via a 4-tier auto-guard that reloads the session. This is the 'auto-compress current context' that context-mode does NOT do — the most direct attack on re-cached bloat. CAVEATS: it MUTATES transcripts + reloads the Claude process (brittle on forks / non-stock configs — esp. with custom CLAUDE_CODE_* compaction env or Agent Teams); disable its SessionStart auto-updater; reconcile its 25/55/80/90% thresholds. Try context-mode + codebase-memory-mcp first; escalate to this."))
    if out_share >= 0.25:
        recs.append(("ponytail", f"~{out_share*100:.0f}% of cost is generated output; ponytail's lazy-senior-dev rules make it write less code."))
    recs.append(("rtk", "targets CLI/tool output. Run `rtk discover --all --since {}` for YOUR concrete missed-savings ceiling and `rtk cc-economics` for realized savings — usually small unless you run many noisy shell commands.".format(a.days)))
    recs.append(("token-savior", "all-in-one MCP: symbol indexing + 34 bash-output compactors + cross-session memory — covers the context/cache AND CLI buckets in one install. Trade-off: it's a persistent MCP (adds manifest tokens every session) and needs python/pip. Consider it INSTEAD of stacking context-mode + codebase-memory-mcp + rtk; measure the MCP overhead in the A/B."))
    for i, (t, why) in enumerate(recs, 1):
        tag = "  *" if i == 1 else "   "
        inst = "  [ALREADY INSTALLED]" if have.get(t) else ""
        pre = ""
        if have.get(t):
            pre = "You already have it — the lever is USAGE, not install. " if t == "context-mode" else "Already installed — "
        print(f"{tag} {i}. {t}{inst}\n      {pre}{why}")

    # Perfect pairings: two tools that attack complementary buckets with little
    # overlap. Only surfaced when the person's numbers actually justify the combo.
    pairings = []
    if cache_dominates and in_share >= 0.10:
        pairings.append(("context-mode + codebase-memory-mcp",
                         "offload big tool OUTPUTS (cm) AND stop re-reading files for discovery (codebase-memory-mcp) — two non-overlapping cuts at your context/cache bill."))
    if cache_dominates and out_share >= 0.25:
        pairings.append(("context-mode + ponytail",
                         "shrink the context you pay to re-read (cm) AND write less code in the first place (ponytail)."))
    pairings.append(("token-savior (single install)",
                     "if you'd otherwise stack context-mode + codebase-memory-mcp + rtk, token-savior bundles indexing + bash compaction + memory in one MCP. One thing to manage, one MCP overhead to measure."))
    print(f"\n{'─'*64}\n  SUGGESTED PAIRINGS (complementary buckets, little overlap):\n{'─'*64}")
    for combo, why in pairings:
        print(f"   • {combo}\n      {why}")

    # Honest ROI calibration: tie the savings ceiling to REAL annualized spend so
    # a tiny real bill doesn't masquerade as a problem worth a tool's overhead.
    annual = cost * 365 / max(a.days, 1)
    ceiling = cache_share * annual
    print(f"\n  ROI check: real interactive spend ~= ${annual:,.0f}/yr. Even a full win on your")
    print(f"  dominant bucket caps savings near ~${ceiling:,.0f}/yr — weigh that against the")
    print(f"  setup/maintenance (and, for proxies, trust) cost before adopting any tool.")

    ab = next((t for t, _ in recs if not have.get(t)), None)
    print()
    if ab:
        print(f"  Next: validate with a PASSIVE A/B during normal interactive use")
        print(f"        (scripts/compare.py --enable {ab}), comparing recorded usage windows.")
        if ab != recs[0][0]:
            print(f"        (#1 '{recs[0][0]}' is already installed — A/B the first not-yet-installed pick.)")
    else:
        print(f"  Next: every recommended tool is already installed — the lever is USAGE,")
        print(f"        not adoption. Use ctx_*/codebase-memory-mcp deliberately; re-run in ~2 weeks to trend cache_read.")
    print()

    if not have.get("codebase-memory-mcp"):
        print(f"  Tip: if you often run Claude Code at HIGH or XHIGH reasoning effort, install")
        print(f"  codebase-memory-mcp regardless of the bucket numbers above — that effort level")
        print(f"  explores via many grep/Read tool calls, and codebase-memory-mcp replaces dozens")
        print(f"  of those round-trips with one graph query. (ccusage/the transcripts don't log")
        print(f"  effort level, so this can't be measured automatically — it's a judgment call.)")
        print()

if __name__ == "__main__":
    main()
