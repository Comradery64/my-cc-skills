#!/usr/bin/env python3
"""cc-token-audit — Phase 3+4: PASSIVE A/B on REAL usage. $0 (reads ccusage, no API).

Compares your real Claude Code sessions BEFORE vs AFTER a tool was enabled. This is
the ONLY valid way to measure a tool's savings on your actual work — headless
`claude -p` replays do NOT reflect interactive use and produce invalid results.

  python3 compare.py --enable context-mode     # mark today as the cutoff, then enable the tool in your real CC
  # ...use Claude Code normally ~1-2 weeks...
  python3 compare.py                            # before/after around the recorded date
  python3 compare.py --project myrepo --window 21
"""
import json, subprocess, argparse, statistics as st, os, datetime as dt, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = os.path.join(HERE, "enabled.json")

def runner():
    if shutil.which("ccusage"): return ["ccusage"]
    if shutil.which("npx"): return ["npx", "-y", "ccusage@latest"]
    sys.exit("ccusage not found. Install: npm i -g ccusage")

def sessions():
    return json.loads(subprocess.check_output(runner()+["session","--json"], text=True)).get("sessions", [])

def date_of(s): return (s.get("lastActivity") or "")[:10]

def summarize(rows, label):
    if not rows: print(f"  {label:8} n=0"); return None
    cost=[r.get("totalCost") or 0 for r in rows]
    cr=[r.get("cacheReadTokens") or 0 for r in rows]
    out=[r.get("outputTokens") or 0 for r in rows]
    med=lambda x: st.median(x) if x else 0; mean=lambda x: sum(x)/len(x) if x else 0
    print(f"  {label:8} n={len(rows):3d} | cost/sess med=${med(cost):7.3f} mean=${mean(cost):7.3f} "
          f"| cacheRead/sess med={med(cr)/1e6:6.2f}M | out/sess med={med(out)/1e3:6.1f}k")
    return {"n":len(rows),"cost_med":med(cost),"cr_med":med(cr)}

def daily_rows(since, until):
    """`ccusage daily --json` rows for [since, until] inclusive. Fallback when
    `ccusage session` returns 0 (CLAUDE_CONFIG_DIR redirect / non-standard transcripts)."""
    try:
        return json.loads(subprocess.check_output(
            runner()+["daily","--json","--since",since,"--until",until], text=True)).get("daily", [])
    except Exception:
        return []

def summarize_daily(rows, label):
    """Per-DAY aggregate (cost/day, cacheRead/day) — weaker than per-session but
    usable when `ccusage session` is blind to the install."""
    days=[r for r in rows if any((m.get("cost") or m.get("cacheReadTokens")) for m in r.get("modelBreakdowns",[]))]
    if not days: print(f"  {label:8} n=0 days"); return None
    cost=[sum((m.get("cost") or 0) for m in r.get("modelBreakdowns",[])) for r in days]
    cr=[sum((m.get("cacheReadTokens") or 0) for m in r.get("modelBreakdowns",[])) for r in days]
    med=lambda x: st.median(x) if x else 0
    print(f"  {label:8} n={len(days):3d}d | cost/day med=${med(cost):7.2f} | cacheRead/day med={med(cr)/1e6:6.2f}M  (daily fallback)")
    return {"n":len(days),"cost_med":med(cost),"cr_med":med(cr)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--enable"); ap.add_argument("--cutoff"); ap.add_argument("--model", default="")
    ap.add_argument("--project", default=""); ap.add_argument("--window", type=int, default=14)
    a=ap.parse_args()
    if a.enable:
        json.dump({"tool":a.enable,"enabled_at":dt.date.today().isoformat()}, open(MARK,"w"))
        print(f"recorded '{a.enable}' enabled_at {dt.date.today().isoformat()}.")
        print("Now enable the tool in your real Claude Code and use it normally; re-run with no args in ~1-2 weeks.")
        return
    cutoff=a.cutoff; tool="?"
    if not cutoff and os.path.exists(MARK):
        m=json.load(open(MARK)); cutoff=m["enabled_at"]; tool=m.get("tool","?")
    if not cutoff: sys.exit("No cutoff. Run `compare.py --enable <tool>` first, or pass --cutoff YYYY-MM-DD.")
    c=dt.date.fromisoformat(cutoff)
    lo=(c-dt.timedelta(days=a.window)).isoformat(); hi=(c+dt.timedelta(days=a.window)).isoformat()
    before_until=(c-dt.timedelta(days=1)).isoformat()
    print(f"Passive A/B  tool={tool}  cutoff={cutoff}  ±{a.window}d  model~='{a.model or '*'}'  project~='{a.project or '*'}'")
    S=[s for s in sessions()
       if (not a.model or a.model in ",".join(s.get("modelsUsed") or []))
       and (not a.project or a.project in (s.get("projectPath") or ""))]
    if S:
        before=[s for s in S if lo<=date_of(s)<cutoff]; after=[s for s in S if cutoff<=date_of(s)<=hi]
        b=summarize(before,"BEFORE"); f=summarize(after,"AFTER")
        if b and f and b["cost_med"]:
            print(f"\n  Δ cost/session (median): {(f['cost_med']/b['cost_med']-1)*100:+.1f}%"
                  f"   Δ cacheRead/session: {(f['cr_med']/b['cr_med']-1)*100:+.1f}%" if b['cr_med'] else "")
            print("  Trust only with n≳15 each side + a like-for-like --project filter (your tasks vary).")
    else:
        # ccusage session is blind to this install (CLAUDE_CONFIG_DIR redirect or
        # non-standard transcripts). Fall back to per-day aggregates.
        print("  (ccusage session returned 0 — daily fallback active. No per-session/--project granularity.)")
        b=summarize_daily(daily_rows(lo, before_until),"BEFORE"); f=summarize_daily(daily_rows(cutoff, hi),"AFTER")
        if b and f and b["cost_med"]:
            extra=f"   Δ cacheRead/day: {(f['cr_med']/b['cr_med']-1)*100:+.1f}%" if b['cr_med'] else ""
            print(f"\n  Δ cost/day (median): {(f['cost_med']/b['cost_med']-1)*100:+.1f}%{extra}")
            print("  DAILY FALLBACK: noisier than per-session (work varies day-to-day). Trust only a clear,")
            print("  sustained shift across the window — not a single-day blip.")

if __name__ == "__main__":
    main()
