#!/usr/bin/env python3
"""Generate daily standup report from git commits."""

import subprocess
import os
from datetime import datetime, timedelta
from pathlib import Path
import re

def find_repos(base_path="/Volumes/SD/Work"):
    """Find all git repositories."""
    repos = []
    for root, dirs, files in os.walk(base_path):
        # Skip hidden dirs and common exclusions (but keep .git itself)
        dirs[:] = [d for d in dirs if not d.startswith('.') or d == '.git']
        dirs[:] = [d for d in dirs if d not in ['node_modules', '__pycache__', 'venv']]
        if '.git' in dirs:
            repos.append(root)
            # Don't descend into .git directory
            dirs[:] = []
    return repos

def get_project_name(repo_path):
    """Extract project name from repo path."""
    basename = os.path.basename(repo_path)
    return basename

def detect_domain(message, repo_path):
    """Detect the logical domain/project from commit content."""
    repo_name = os.path.basename(repo_path).lower()
    msg_lower = message.lower()

    # Check for trainium-specific work
    if any(x in msg_lower for x in ['trainium', 'sglang', 'vendor account', 'external vendor']):
        return 'Trainium'

    # Check for testing-platform specific work
    if any(x in msg_lower for x in ['testing-platform', 'testing platform']):
        return 'Testing Platform'

    # Check for org/IAM work (cross-cutting) — but not if it's vendor-scoped
    if any(x in msg_lower for x in ['scp', 'organization']) and 'vendor' not in msg_lower:
        return 'Organization'

    # Check for data-lake work
    if 'data-lake' in msg_lower:
        return 'Data Lake'

    # Check for gateway work
    if 'gateway' in msg_lower:
        return 'Gateway'

    # Repo-specific detection
    if 'trainium' in repo_name:
        return 'Trainium'

    # Default to repo name
    if repo_name == 'company-infra':
        return 'Infra'

    return repo_name.replace('-', ' ').title()

def get_commits(repo_path, hours=24):
    """Get commits from the past N hours, with domain context."""
    try:
        since = f"{hours} hours ago"
        result = subprocess.run(
            ['git', 'log', f'--since={since}', '--oneline', '--pretty=format:%s'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            commits = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    domain = detect_domain(line, repo_path)
                    commits.append((line.strip(), domain))
            return commits
    except Exception as e:
        pass
    return []

def should_skip(message):
    """Filter out noise commits."""
    skip_patterns = [
        r'^Merge',
        r'^Revert',
        r'^docs:',
        r'^chore:(?!.*[a-z]{10})',
    ]

    for pattern in skip_patterns:
        if re.match(pattern, message, re.IGNORECASE):
            return True

    if len(message.split()) < 3:
        return True

    return False

def clean_message(message):
    """Clean up commit message for standup."""
    # Remove type prefix (feat:, fix:, etc.)
    message = re.sub(r'^(feat|fix|refactor|perf|style|test|chore|docs)\s*\(([^)]+)\):\s*', '', message)
    message = re.sub(r'^(feat|fix|refactor|perf|style|test|chore|docs):\s*', '', message)

    # Remove PR references
    message = re.sub(r'\s*\(#\d+\)\s*$', '', message)
    message = re.sub(r'\s*#\d+\s*$', '', message)

    # Remove excessive parenthetical scope info
    message = re.sub(r'^\(([^)]+)\)\s*', '', message)

    # Simplify S3/IAM jargon: s3:GetBucketPublicAccessBlock etc -> IAM updates
    if re.search(r's3:[A-Za-z]+(Public|Access|Cors|Bucket)', message):
        message = 'IAM and S3 policy updates'

    # Simplify: "move X to managed policy to stay under Y limit" -> simpler
    message = re.sub(r'move .* to managed policy.*', 'Consolidated IAM policies', message, flags=re.IGNORECASE)

    # Capitalize
    if message and message[0].islower():
        message = message[0].upper() + message[1:]

    # Truncate if too long
    if len(message) > 80:
        message = message[:77] + '...'

    return message.strip()


def smart_deduplicate(items):
    """Remove duplicates and merge similar items intelligently.

    items: list of (message, domain) tuples
    returns: list of (message, domain) tuples
    """
    # First pass: remove exact duplicates, keep first occurrence
    seen = {}
    deduplicated = []
    for msg, domain in items:
        key = (msg.lower(), domain)
        if key not in seen:
            seen[key] = True
            deduplicated.append((msg, domain))

    # Second pass: group by (domain, topic) to find related commits within the same domain
    groups = {}

    for msg, domain in deduplicated:
        # Determine topic based on keywords
        topic = None

        if any(x in msg.lower() for x in ['s3', 'iam', 'policy', 'role', 'permission']):
            topic = 'iam'
        elif 'ap-southeast' in msg.lower() or 'region' in msg.lower():
            topic = 'regions'
        elif any(x in msg.lower() for x in ['testing-platform', 'testing platform', 'rds', 'database']):
            topic = 'infrastructure'
        elif 'tailscale' in msg.lower() or 'ecs' in msg.lower():
            topic = 'deployment'
        else:
            topic = msg.split()[0] if msg else 'other'

        # Group key is domain + topic for better dedup
        group_key = (domain, topic)

        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append((msg, domain))

    # For each group, keep only the first message
    result = []
    for group_key in sorted(groups.keys()):
        items_list = groups[group_key]
        # Keep the first occurrence
        result.append(items_list[0])

    return result


def get_standup_window(days_back=0):
    """Get the standup time window: 7:55 PM yesterday to 7:55 PM today.

    Args:
        days_back: How many days back to go (0=today, 1=yesterday, 2=day before yesterday)

    If called before 7:55 PM, shows the previous standup window (day before yesterday to yesterday).
    If called at/after 7:55 PM, shows today's standup window (yesterday to today).
    """
    from datetime import datetime, time, timedelta

    now = datetime.now()
    standup_time = time(19, 55)  # 7:55 PM

    if now.time() >= standup_time:
        # After 7:55 PM: show yesterday 7:55 PM to today 7:55 PM
        start = now.replace(hour=19, minute=55, second=0, microsecond=0) - timedelta(days=1 + days_back)
        end = now.replace(hour=19, minute=55, second=0, microsecond=0) - timedelta(days=days_back)
    else:
        # Before 7:55 PM: show day before yesterday 7:55 PM to yesterday 7:55 PM
        start = now.replace(hour=19, minute=55, second=0, microsecond=0) - timedelta(days=2 + days_back)
        end = now.replace(hour=19, minute=55, second=0, microsecond=0) - timedelta(days=1 + days_back)

    return start, end

def get_commits_in_window(repo_path, start_time, end_time):
    """Get commits between two specific times."""
    try:
        result = subprocess.run(
            ['git', 'log',
             f'--since={start_time.isoformat()}',
             f'--until={end_time.isoformat()}',
             '--oneline', '--pretty=format:%s'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            commits = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    domain = detect_domain(line, repo_path)
                    commits.append((line.strip(), domain))
            return commits
    except Exception as e:
        pass
    return []

def generate_standup(hours=None, days_back=0):
    """Generate standup report.

    Args:
        hours: If specified, use hours-based window (backward compatible)
        days_back: How many days back (0=today, 1=yesterday, 2=day before yesterday)

    If hours is specified, use that window (backward compatible).
    Otherwise, use the 7:55 PM to 7:55 PM window.
    """
    all_commits = []

    repos = find_repos()
    if not repos:
        return "No git repositories found in /Volumes/SD/Work"

    # Get the standup time window
    if hours is None:
        start_time, end_time = get_standup_window(days_back=days_back)

        # Collect commits from all repos using the time window
        for repo in repos:
            commits = get_commits_in_window(repo, start_time, end_time)
            all_commits.extend(commits)

        if days_back == 0:
            period_str = f"7:55 PM yesterday to 7:55 PM today"
        elif days_back == 1:
            period_str = f"7:55 PM two days ago to 7:55 PM yesterday"
        else:
            period_str = f"7:55 PM {days_back+1} days ago to 7:55 PM {days_back} days ago"
    else:
        # Legacy: use hours-based window
        for repo in repos:
            commits = get_commits(repo, hours)
            all_commits.extend(commits)
        period_str = f"Last {hours} hours"

    # Filter and clean (handling tuples)
    filtered = [(msg, domain) for msg, domain in all_commits if not should_skip(msg)]
    cleaned = [(clean_message(msg), domain) for msg, domain in filtered]
    cleaned = [(msg, domain) for msg, domain in cleaned if msg]  # Remove empties

    # Deduplicate
    unique = smart_deduplicate(cleaned)
    # Sort by domain then message
    unique.sort(key=lambda x: (x[1], x[0]))

    if not unique:
        return f"No significant commits in the selected window"

    # Format as bullets with domain name
    report = "Daily Standup Report\n"
    report += f"Period: {period_str}\n"
    report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += "\n"

    # Format with domain label only on first item per domain
    current_domain = None
    for item, domain in unique:
        if domain != current_domain:
            report += f"[{domain}] {item}\n"
            current_domain = domain
        else:
            report += f"{item}\n"

    return report

if __name__ == '__main__':
    import sys
    from datetime import datetime as dt

    args = sys.argv[1:]
    hours = None
    days_back = 0
    since_str = None
    until_str = None

    i = 0
    while i < len(args):
        if args[i] == '--since' and i + 1 < len(args):
            since_str = args[i + 1]
            i += 2
        elif args[i] == '--until' and i + 1 < len(args):
            until_str = args[i + 1]
            i += 2
        elif args[i] in ['--previous', '-p', 'previous', 'yesterday']:
            days_back = 1
            i += 1
        else:
            try:
                hours = int(args[i])
            except ValueError:
                pass
            i += 1

    if since_str and until_str:
        start_time = dt.fromisoformat(since_str)
        end_time = dt.fromisoformat(until_str)
        all_commits = []
        repos = find_repos()
        for repo in repos:
            all_commits.extend(get_commits_in_window(repo, start_time, end_time))
        filtered = [(msg, domain) for msg, domain in all_commits if not should_skip(msg)]
        cleaned = [(clean_message(msg), domain) for msg, domain in filtered]
        cleaned = [(msg, domain) for msg, domain in cleaned if msg]
        unique = smart_deduplicate(cleaned)
        unique.sort(key=lambda x: (x[1], x[0]))
        print(f"Daily Standup Report")
        print(f"Period: {start_time.strftime('%b %d %I:%M %p')} to {end_time.strftime('%b %d %I:%M %p')}")
        print(f"Generated: {dt.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        if not unique:
            print("No significant commits in the selected window")
        else:
            current_domain = None
            for item, domain in unique:
                if domain != current_domain:
                    print(f"[{domain}] {item}")
                    current_domain = domain
                else:
                    print(item)
    else:
        print(generate_standup(hours=hours, days_back=days_back))
