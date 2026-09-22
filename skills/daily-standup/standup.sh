#!/bin/bash
set -euo pipefail

# daily-standup: Generate standup summary for a given date
# Usage: ./standup.sh [date]
# Date format: YYYY-MM-DD (default: today)

TARGET_DATE="${1:-$(date +%Y-%m-%d)}"

BASE_DIR="/Volumes/SD/Work"

# Find all git repos
repos=$(find "$BASE_DIR" -maxdepth 2 -name ".git" -type d 2>/dev/null | sed 's|/.git||' | sort)

found_any=false

for repo in $repos; do
  repo_name=$(basename "$repo")
  cd "$repo"
  
  # Get commits for the date
  commits=$(git log --all --since="$TARGET_DATE 00:00" --until="$TARGET_DATE 23:59" --pretty=format:"%H" 2>/dev/null || true)
  
  if [ -n "$commits" ]; then
    found_any=true
    echo "**$repo_name**"
    
    # Get full commit info
    git log --all --since="$TARGET_DATE 00:00" --until="$TARGET_DATE 23:59" --format="%s" 2>/dev/null | head -20 | sed 's/^/- /'
    echo ""
  fi
done

if [ "$found_any" = false ]; then
  echo "No commits found on $TARGET_DATE"
  exit 0
fi
