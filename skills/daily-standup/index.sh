#!/bin/bash
# daily-standup skill — emit raw git material for Claude to synthesize
# Usage: index.sh [YYYY-MM-DD]
#   No arg:          START = yesterday 20:00, END = today 20:00
#   With date:       START = that date 20:00, END = next day 20:00
# 8pm (20:00) cutoff: work after 8pm counts toward the next day.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$HOME/Dev/Work"

# ── usage ──────────────────────────────────────────────────────────────────
usage() {
  echo "Usage: $(basename "$0") [YYYY-MM-DD]"
  echo ""
  echo "  No argument   : window = yesterday 20:00 → today 20:00"
  echo "  YYYY-MM-DD    : window = that date 20:00 → next day 20:00"
  echo ""
  echo "Options:"
  echo "  -h, --help    : print this message and exit"
}

# ── date helpers ────────────────────────────────────────────────────────────
# Prefer gdate (GNU coreutils) for reliable -d arithmetic; fall back to BSD date -v
if command -v /opt/homebrew/bin/gdate &>/dev/null; then
  _date() { /opt/homebrew/bin/gdate "$@"; }
elif command -v gdate &>/dev/null; then
  _date() { gdate "$@"; }
else
  # BSD date fallback — translate -d "X + 1 day" → -v+1d
  _date() {
    # We only need two forms:
    #   _date -d "YYYY-MM-DD + 1 day" +%Y-%m-%d
    #   _date +%Y-%m-%d
    if [[ "${1:-}" == "-d" ]]; then
      local spec="$2"
      local fmt="${3:-%Y-%m-%d}"
      if [[ "$spec" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}).*\+\ *1\ *day ]]; then
        local base="${BASH_REMATCH[1]}"
        date -j -v+1d -f "%Y-%m-%d" "$base" "$fmt"
      elif [[ "$spec" =~ ([0-9]{4}-[0-9]{2}-[0-9]{2}).*-\ *1\ *day ]]; then
        local base="${BASH_REMATCH[1]}"
        date -j -v-1d -f "%Y-%m-%d" "$base" "$fmt"
      else
        date -j -f "%Y-%m-%d" "$spec" "$fmt" 2>/dev/null
      fi
    else
      date "$@"
    fi
  }
fi

# ── argument parsing ────────────────────────────────────────────────────────
DATE_ARG=""
for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0 ;;
    -*)        echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
    *)         DATE_ARG="$arg" ;;
  esac
done

# ── compute window ──────────────────────────────────────────────────────────
if [ -z "$DATE_ARG" ]; then
  # No arg: yesterday 20:00 → today 20:00
  TODAY=$(_date +%Y-%m-%d)
  YESTERDAY=$(_date -d "$TODAY - 1 day" +%Y-%m-%d)
  START="$YESTERDAY 20:00:00"
  END="$TODAY 20:00:00"
  START_ISO="${YESTERDAY}T20:00:00"
  END_ISO="${TODAY}T20:00:00"
  END_LABEL="$TODAY"
else
  # Validate format YYYY-MM-DD
  if ! [[ "$DATE_ARG" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "Error: date must be YYYY-MM-DD, got: $DATE_ARG" >&2
    usage >&2
    exit 2
  fi
  # Validate the date is actually calendar-valid
  if ! _date -d "$DATE_ARG + 0 day" +%Y-%m-%d &>/dev/null; then
    echo "Error: invalid date: $DATE_ARG" >&2
    usage >&2
    exit 2
  fi
  NEXT_DAY=$(_date -d "$DATE_ARG + 1 day" +%Y-%m-%d 2>/dev/null)
  if [ -z "$NEXT_DAY" ]; then
    echo "Error: could not compute next day for: $DATE_ARG" >&2
    exit 2
  fi
  START="$DATE_ARG 20:00:00"
  END="$NEXT_DAY 20:00:00"
  START_ISO="${DATE_ARG}T20:00:00"
  END_ISO="${NEXT_DAY}T20:00:00"
  END_LABEL="$NEXT_DAY"
fi

echo "# Daily Standup — window: $START → $END"
echo ""

# ── repo scan ───────────────────────────────────────────────────────────────
found_commits=false

while IFS= read -r git_dir; do
  repo="${git_dir%/.git}"
  repo_name="$(basename "$repo")"

  # Get commits in window (subject + full body)
  commit_out="$(
    git -C "$repo" log --all \
      --since="$START" --until="$END" \
      --pretty=format:"commit %H%nauthor %an <%ae>%ndate %ai%nsubject %s%n%nbody:%n%b%n---END---" \
      2>/dev/null || true
  )"

  if [ -n "$commit_out" ]; then
    found_commits=true
    echo "## $repo_name"
    echo ""
    # Generous cap — Claude needs full detail; truncate only runaway repos
    printf '%s\n' "$commit_out" | head -200
    echo ""
  fi
done < <(find "$BASE_DIR" -maxdepth 2 -name ".git" -type d 2>/dev/null | sort)

# ── work in progress ─────────────────────────────────────────────────────────
wip_out=""
while IFS= read -r git_dir; do
  repo="${git_dir%/.git}"
  repo_name="$(basename "$repo")"
  status_out="$(git -C "$repo" status --short 2>/dev/null || true)"
  if [ -n "$status_out" ]; then
    wip_out+="### $repo_name"$'\n'
    wip_out+="$status_out"$'\n'$'\n'
  fi
done < <(find "$BASE_DIR" -maxdepth 2 -name ".git" -type d 2>/dev/null | sort)

if [ -n "$wip_out" ]; then
  echo "## Work in progress (uncommitted)"
  echo ""
  printf '%s' "$wip_out"
fi

# ── bee hook ─────────────────────────────────────────────────────────────────
bee_out=""
if [ -x "$SKILL_DIR/bee-capture.sh" ]; then
  bee_out="$(bash "$SKILL_DIR/bee-capture.sh" "$START_ISO" "$END_ISO" 2>/dev/null || true)"
  if [ -n "$bee_out" ]; then
    printf '\n## IT Manager / Ops (Bee)\n\n%s\n' "$bee_out"
  fi
fi

# ── nothing found ────────────────────────────────────────────────────────────
if [ "$found_commits" = false ] && [ -z "$wip_out" ] && [ -z "$bee_out" ]; then
  echo "No activity found from $START to $END"
fi
