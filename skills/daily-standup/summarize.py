#!/usr/bin/env python3
"""Extract high-level work summaries from JSONL transcripts."""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def extract_summaries(date_str, projects_dir):
    """Extract meaningful work summaries from transcripts."""
    work = defaultdict(list)

    for proj_dir in projects_dir.glob("*Dev-Work*"):
        proj_name = proj_dir.name.replace("-Users-alan-livshin-Dev-Work-", "").replace("--claude-worktrees-", "/")

        for jsonl_file in proj_dir.rglob("*.jsonl"):
            stat = jsonl_file.stat()
            file_date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
            if file_date != date_str:
                continue

            try:
                with open(jsonl_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                        except:
                            continue

                        # Extract assistant summaries
                        if entry.get("type") == "assistant":
                            msg = entry.get("message", {})
                            content = msg.get("content", [])

                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict):
                                        text = item.get("text", "").strip()

                                        # Look for summary-like text (contains accomplishment keywords)
                                        if text and any(keyword in text for keyword in
                                            ["✅", "Done", "created", "fixed", "added", "implemented",
                                             "updated", "resolved", "integrated", "configured", "deployed"]):
                                            # Extract first 2-3 sentences max
                                            sentences = text.split('. ')[:2]
                                            summary = '. '.join(sentences).strip()[:200]
                                            if len(summary) > 30:  # Only meaningful summaries
                                                work[proj_name].append(summary)
            except:
                pass

    return work

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    projects_dir = Path.home() / ".claude" / "projects"

    work = extract_summaries(date, projects_dir)

    if not work:
        print(f"No work recorded for {date}")
        return

    # Print by project, deduplicated summaries
    for proj_name in sorted(work.keys()):
        items = work[proj_name]
        # Deduplicate similar items
        unique = []
        for item in items:
            if not any(item in u or u in item for u in unique):
                unique.append(item)

        if unique:
            print(f"\n**{proj_name}**")
            for summary in unique[:3]:  # Top 3 per project
                # Clean up markdown bullets
                summary = summary.lstrip("- ✅ •").strip()
                print(f"• {summary}")

if __name__ == "__main__":
    main()
