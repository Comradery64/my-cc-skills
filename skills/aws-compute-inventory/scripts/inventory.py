#!/usr/bin/env python3
"""
AWS multi-account compute + cost inventory.

Counts vCPUs across every account in the org, broken down by compute type
(EC2, ECS-Fargate, EKS, RDS), and pulls a cost breakdown (by account and by
service) from Cost Explorer in the payer (management) account.

Design notes / hard-won lessons baked in here:
  * SCPs never restrict the management account, and the Trainium account is not
    region-confined either -- so we sweep ALL enabled regions per account, not
    just us-west-1/us-east-1. (Found mgmt instances in us-west-2/us-east-2 and a
    Trainium instance in ap-southeast-4 that a two-region scan missed.)
  * EC2 vCPU = CpuOptions.CoreCount * ThreadsPerCore -- exact, no type lookup.
  * ECS: only FARGATE-launch tasks add vCPUs. EC2-launch tasks run ON ec2
    instances we've already counted, so counting them would double-count.
  * EKS: managed/self-managed nodes ARE ec2 instances (already counted). Only
    Fargate pods would be additive, and pod vCPU needs the k8s API -- so we flag
    Fargate profiles for manual follow-up rather than guessing.
  * RDS vCPU: DB classes mirror EC2 types (db.r6g.large <-> r6g.large). We look
    up vCPU via ec2 describe-instance-types. The field is VCpuInfo.DefaultVCpus
    (capital V AND C -- "DefaultVcpus" silently returns null).

Uses the AWS CLI under the hood (no boto3 dependency). Reuses your SSO session;
run `aws sso login --profile mgmt-admin` first if creds are stale.
"""

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import subprocess
import sys
from collections import defaultdict

# --- Account map. Update here if the org changes. --- (example values below; replace with your own)
# Most accounts have a named SSO profile. Trainium has no profile, so we assume
# OrganizationAccountAccessRole into it from the management profile.
ACCOUNTS = [
    {"label": "management",      "id": "333333333333", "profile": "mgmt-admin",            "payer": True},
    {"label": "identity",        "id": "222222222222", "profile": "identity-admin"},
    {"label": "shared-services", "id": "444444444444", "profile": "shared-services-admin"},
    {"label": "dev",             "id": "111111111111", "profile": "dev-admin"},
    {"label": "staging",         "id": "555555555555", "profile": "staging-admin"},
    {"label": "prod",            "id": "666666666666", "profile": "prod-admin"},
    {"label": "logging",         "id": "777777777777", "profile": "logging-admin"},
    {"label": "trainium",        "id": "888888888888",
     "assume_role_arn": "arn:aws:iam::888888888888:role/OrganizationAccountAccessRole",
     "assume_from_profile": "mgmt-admin"},
]
ID_TO_LABEL = {a["id"]: a["label"] for a in ACCOUNTS}

# Regions we always full-scan for ECS/RDS even if they show no EC2, because
# Fargate services and databases can exist in a region with zero EC2 instances.
BASELINE_REGIONS = ["us-west-1", "us-east-1"]
CE_REGION = "us-east-1"  # Cost Explorer endpoint


def run_aws(args, env_extra, timeout=120):
    """Run an aws CLI command, return parsed JSON (or None on failure)."""
    import os
    env = os.environ.copy()
    env.update(env_extra)
    cmd = ["aws"] + args + ["--output", "json"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if p.returncode != 0:
        return None
    if not p.stdout.strip():
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def creds_for(account):
    """Return an env dict that authenticates as the given account."""
    if "profile" in account:
        return {"AWS_PROFILE": account["profile"]}
    # Cross-account assume (Trainium).
    out = run_aws(
        ["sts", "assume-role",
         "--role-arn", account["assume_role_arn"],
         "--role-session-name", "compute-inventory"],
        {"AWS_PROFILE": account["assume_from_profile"]},
    )
    if not out:
        return None
    c = out["Credentials"]
    return {
        "AWS_ACCESS_KEY_ID": c["AccessKeyId"],
        "AWS_SECRET_ACCESS_KEY": c["SecretAccessKey"],
        "AWS_SESSION_TOKEN": c["SessionToken"],
    }


def enabled_regions(creds):
    out = run_aws(["ec2", "describe-regions", "--region", "us-east-1",
                   "--query", "Regions[].RegionName"], creds)
    return out or []


def count_running_ec2(creds, region):
    out = run_aws(["ec2", "describe-instances", "--region", region,
                   "--filters", "Name=instance-state-name,Values=running",
                   "--query", "length(Reservations[].Instances[])"], creds)
    try:
        return int(out) if out is not None else 0
    except (TypeError, ValueError):
        return 0


def scan_ec2(creds, region):
    """Return {instance_type: [count, vcpus]} for running instances."""
    out = run_aws(["ec2", "describe-instances", "--region", region,
                   "--filters", "Name=instance-state-name,Values=running",
                   "--query",
                   "Reservations[].Instances[].[InstanceType,CpuOptions.CoreCount,CpuOptions.ThreadsPerCore]"],
                  creds)
    by_type = defaultdict(lambda: [0, 0])
    for row in out or []:
        itype, cores, tpc = row[0], row[1], row[2]
        v = (cores or 0) * (tpc or 0)
        by_type[itype][0] += 1
        by_type[itype][1] += v
    return by_type


def scan_ecs_fargate(creds, region):
    """Return (task_count, vcpus) for RUNNING Fargate tasks."""
    clusters = run_aws(["ecs", "list-clusters", "--region", region,
                        "--query", "clusterArns"], creds) or []
    total_v, total_n = 0.0, 0
    for cluster in clusters:
        arns = run_aws(["ecs", "list-tasks", "--cluster", cluster, "--region", region,
                        "--desired-status", "RUNNING", "--query", "taskArns"], creds) or []
        # describe-tasks takes up to 100 task ARNs at a time.
        for i in range(0, len(arns), 100):
            batch = arns[i:i + 100]
            if not batch:
                continue
            tasks = run_aws(["ecs", "describe-tasks", "--cluster", cluster, "--region", region,
                             "--tasks", *batch,
                             "--query", "tasks[].[launchType,cpu]"], creds) or []
            for lt, cpu in tasks:
                if lt == "FARGATE" and cpu:
                    total_v += int(cpu) / 1024.0
                    total_n += 1
    return total_n, total_v


def scan_eks(creds, region):
    """Return list of {cluster, nodegroups, fargate_profiles}."""
    clusters = run_aws(["eks", "list-clusters", "--region", region,
                        "--query", "clusters"], creds) or []
    result = []
    for c in clusters:
        ngs = run_aws(["eks", "list-nodegroups", "--cluster-name", c, "--region", region,
                       "--query", "nodegroups"], creds) or []
        fps = run_aws(["eks", "list-fargate-profiles", "--cluster-name", c, "--region", region,
                       "--query", "fargateProfileNames"], creds) or []
        result.append({"cluster": c, "nodegroups": ngs, "fargate_profiles": fps})
    return result


def scan_rds(creds, region):
    """Return {db_class: count} for available DB instances."""
    out = run_aws(["rds", "describe-db-instances", "--region", region,
                   "--query", "DBInstances[].DBInstanceClass"], creds) or []
    classes = defaultdict(int)
    for cls in out:
        classes[cls] += 1
    return classes


def rds_vcpu_map(creds, region, db_classes):
    """Map db.<type> -> vCPU via ec2 describe-instance-types (DefaultVCpus)."""
    ec2_types = sorted({c.replace("db.", "", 1) for c in db_classes})
    if not ec2_types:
        return {}
    out = run_aws(["ec2", "describe-instance-types", "--region", region,
                   "--instance-types", *ec2_types,
                   "--query", "InstanceTypes[].[InstanceType,VCpuInfo.DefaultVCpus]"], creds) or []
    m = {f"db.{t}": v for t, v in out}
    return m


def inventory_account(account):
    """Full inventory for one account across all relevant regions."""
    creds = creds_for(account)
    label = account["label"]
    if creds is None:
        return {"label": label, "error": "could not authenticate", "ec2": {}, "ecs": {},
                "eks": [], "rds": {}, "regions": []}

    regions = enabled_regions(creds)
    # Fast count sweep to find regions with EC2, in parallel.
    active = set(BASELINE_REGIONS)
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for region, n in zip(regions, ex.map(lambda r: count_running_ec2(creds, r), regions)):
            if n > 0:
                active.add(region)
    active = [r for r in active if r in regions or r in BASELINE_REGIONS]

    ec2 = defaultdict(lambda: [0, 0])           # region -> {type: [n, vcpu]}  flattened below
    ec2_by_region = {}
    ecs = {}
    eks = []
    rds = {}
    for region in sorted(active):
        bt = scan_ec2(creds, region)
        if bt:
            ec2_by_region[region] = {k: v for k, v in bt.items()}
        n, v = scan_ecs_fargate(creds, region)
        if n:
            ecs[region] = {"tasks": n, "vcpus": v}
        e = scan_eks(creds, region)
        if e:
            eks.extend([{**x, "region": region} for x in e])
        rc = scan_rds(creds, region)
        if rc:
            vmap = rds_vcpu_map(creds, region, rc.keys())
            rds[region] = {cls: {"count": cnt, "vcpu_each": vmap.get(cls, 0)}
                           for cls, cnt in rc.items()}
    return {"label": label, "regions": sorted(active),
            "ec2": ec2_by_region, "ecs": ecs, "eks": eks, "rds": rds}


def get_costs(payer_account, months=3):
    """Cost-by-account and cost-by-service from Cost Explorer (payer account)."""
    creds = creds_for(payer_account)
    today = dt.date.today()
    start = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)
    for _ in range(months - 1):
        start = (start - dt.timedelta(days=1)).replace(day=1)
    end = (today.replace(day=1) + dt.timedelta(days=32)).replace(day=1)  # first of next month
    tp = f"Start={start.isoformat()},End={end.isoformat()}"

    # CRITICAL: filter to RECORD_TYPE=Usage. This org's accounts are fully
    # covered by credits, so unfiltered UnblendedCost nets to ~$0 (credits
    # offset usage) and grouping by LINKED_ACCOUNT shows every account at $0.
    # Filtering to Usage strips credits/refunds/tax and reveals real spend
    # (e.g. dev ~$11.6k/mo from the big m7i instance). Without this filter the
    # cost report is meaningless.
    usage_only = '{"Dimensions":{"Key":"RECORD_TYPE","Values":["Usage"]}}'

    def query(group_key):
        return run_aws(["ce", "get-cost-and-usage", "--region", CE_REGION,
                        "--time-period", tp, "--granularity", "MONTHLY",
                        "--metrics", "UnblendedCost", "--filter", usage_only,
                        "--group-by", f"Type=DIMENSION,Key={group_key}"], creds, timeout=180)

    by_acct = query("LINKED_ACCOUNT")
    by_svc = query("SERVICE")
    return {"time_period": tp, "by_account": by_acct, "by_service": by_svc}


# --- Reporting -----------------------------------------------------------------

def build_report(accounts_data, costs):
    EC2_T = ECS_T = RDS_T = 0
    per_acct = defaultdict(lambda: {"ec2": 0, "ecs": 0.0, "rds": 0})
    eks_flags, errors = [], []

    for d in accounts_data:
        label = d["label"]
        if d.get("error"):
            errors.append(f"{label}: {d['error']}")
        for region, types in d["ec2"].items():
            for _, (n, v) in types.items():
                per_acct[label]["ec2"] += v
                EC2_T += v
        for region, info in d["ecs"].items():
            per_acct[label]["ecs"] += info["vcpus"]
            ECS_T += info["vcpus"]
        for region, classes in d["rds"].items():
            for cls, info in classes.items():
                rv = info["count"] * info["vcpu_each"]
                per_acct[label]["rds"] += rv
                RDS_T += rv
        for e in d["eks"]:
            if e["fargate_profiles"]:
                eks_flags.append(f"{label}/{e['region']} cluster {e['cluster']}: "
                                 f"Fargate profiles {e['fargate_profiles']} (pod vCPU not counted)")

    lines = []
    lines.append("# Multi-account compute + cost inventory")
    lines.append(f"_Generated {dt.date.today().isoformat()} — running resources, point-in-time._\n")

    lines.append("## vCPUs by compute type\n")
    lines.append("| Type | vCPUs |")
    lines.append("|---|---:|")
    lines.append(f"| EC2 | {round(EC2_T)} |")
    lines.append(f"| ECS (Fargate) | {round(ECS_T)} |")
    lines.append(f"| RDS | {round(RDS_T)} |")
    lines.append(f"| EKS | 0 (nodes counted under EC2) |")
    lines.append(f"| **Total** | **{round(EC2_T + ECS_T + RDS_T)}** |\n")

    lines.append("## vCPUs by account\n")
    lines.append("| Account | EC2 | ECS-Far | RDS | Total |")
    lines.append("|---|---:|---:|---:|---:|")
    for label in sorted(per_acct, key=lambda l: -(per_acct[l]["ec2"] + per_acct[l]["ecs"] + per_acct[l]["rds"])):
        a = per_acct[label]
        tot = a["ec2"] + a["ecs"] + a["rds"]
        if tot == 0:
            continue
        lines.append(f"| {label} | {round(a['ec2'])} | {round(a['ecs'])} | {round(a['rds'])} | {round(tot)} |")
    lines.append(f"| **Total** | **{round(EC2_T)}** | **{round(ECS_T)}** | **{round(RDS_T)}** | **{round(EC2_T+ECS_T+RDS_T)}** |\n")

    # Cost by account
    if costs and costs.get("by_account"):
        lines.append("## Cost by account (monthly usage charges, excl. credits/refunds/tax)\n")
        results = costs["by_account"].get("ResultsByTime", [])
        months = [r["TimePeriod"]["Start"] for r in results]
        header = "| Account | " + " | ".join(months) + " |"
        lines.append(header)
        lines.append("|---" + "|---:" * len(months) + "|")
        acct_month = defaultdict(lambda: defaultdict(float))
        for r in results:
            m = r["TimePeriod"]["Start"]
            for g in r.get("Groups", []):
                acct_id = g["Keys"][0]
                amt = float(g["Metrics"]["UnblendedCost"]["Amount"])
                acct_month[acct_id][m] += amt
        totals = defaultdict(float)
        for acct_id in sorted(acct_month, key=lambda a: -sum(acct_month[a].values())):
            label = ID_TO_LABEL.get(acct_id, acct_id)
            cells = []
            for m in months:
                v = acct_month[acct_id].get(m, 0.0)
                totals[m] += v
                cells.append(f"${v:,.0f}")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines.append(f"| **Total** | " + " | ".join(f"**${totals[m]:,.0f}**" for m in months) + " |\n")

    # Cost by service (latest full month, top 12)
    if costs and costs.get("by_service"):
        results = costs["by_service"].get("ResultsByTime", [])
        if results:
            last = results[-1]
            m = last["TimePeriod"]["Start"]
            svc = [(g["Keys"][0], float(g["Metrics"]["UnblendedCost"]["Amount"]))
                   for g in last.get("Groups", [])]
            svc.sort(key=lambda x: -x[1])
            lines.append(f"## Top services by cost ({m})\n")
            lines.append("| Service | Cost |")
            lines.append("|---|---:|")
            for name, amt in svc[:12]:
                if amt < 0.01:
                    continue
                lines.append(f"| {name} | ${amt:,.0f} |")
            lines.append("")

    if eks_flags:
        lines.append("## EKS Fargate (manual follow-up — pod vCPU not counted)\n")
        for f in eks_flags:
            lines.append(f"- {f}")
        lines.append("")
    if errors:
        lines.append("## Access errors\n")
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="AWS multi-account compute + cost inventory")
    ap.add_argument("--no-cost", action="store_true", help="skip Cost Explorer query")
    ap.add_argument("--json", metavar="PATH", help="also write raw data as JSON")
    ap.add_argument("--months", type=int, default=3, help="months of cost history (default 3)")
    args = ap.parse_args()

    print("Scanning accounts (parallel region sweeps)...", file=sys.stderr)
    with cf.ThreadPoolExecutor(max_workers=len(ACCOUNTS)) as ex:
        accounts_data = list(ex.map(inventory_account, ACCOUNTS))

    costs = None
    if not args.no_cost:
        print("Querying Cost Explorer (payer account)...", file=sys.stderr)
        payer = next((a for a in ACCOUNTS if a.get("payer")), None)
        if payer:
            costs = get_costs(payer, months=args.months)

    report = build_report(accounts_data, costs)
    print(report)

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"accounts": accounts_data, "costs": costs}, f, indent=2, default=str)
        print(f"\n_Raw data written to {args.json}_", file=sys.stderr)


if __name__ == "__main__":
    main()
