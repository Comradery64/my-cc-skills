#!/bin/bash
# bee-capture.sh — Bee AI-wearable notes capture for daily-standup skill
#
# STATUS: NOT YET VERIFIED — `bee` is not installed on this machine as of this
# writing (2026-06-16). The output format of `bee today` is unconfirmed; the
# parsing in the emit step below is a best-effort pass-through and should be
# revisited once bee is installed and real output has been observed.
#
# Setup required to activate:
#   1. Install the Bee CLI (https://bee.computer — Developer Mode in iOS app).
#   2. Run `bee login` once to authenticate.
#   3. Enable Developer Mode in the Bee iOS app (Settings → Developer).
#   4. Optional: `bee proxy` starts a local HTTP API on :3000 as a fallback.
#
# This script is intentionally a no-op until `bee` exists in PATH, so it is
# safe to ship now — the git standup is completely unaffected by bee's absence.
#
# Contract:
#   Args : $1 = start ISO timestamp, $2 = end ISO timestamp (accepted but
#          bee today is day-scoped, so they are not forwarded to bee directly).
#   Stdout: clean markdown bullet lines ("- ..."), one fact per line, NO header.
#   On any failure / absence / empty output: prints nothing, exits 0.

set -uo pipefail

# --- 1. Require bee in PATH; silently no-op if absent ---
command -v bee >/dev/null 2>&1 || exit 0

# Accept args (unused directly — bee today is day-scoped)
_START="${1:-}"
_END="${2:-}"

# --- 2. Capture `bee today`; swallow stderr; survive non-zero exit ---
raw="$(bee today 2>/dev/null || true)"

# --- 3. Nothing from bee → silent exit ---
if [[ -z "${raw// /}" ]]; then
  exit 0
fi

# --- 4. Emit as markdown bullets ---
# If a line already starts with "- " or "* ", pass it through unchanged.
# Otherwise prefix non-empty lines with "- ".
while IFS= read -r line; do
  # Skip blank lines
  [[ -z "${line// /}" ]] && continue
  # Already bulleted?
  if [[ "$line" == "- "* || "$line" == "* "* ]]; then
    printf '%s\n' "$line"
  else
    printf '- %s\n' "$line"
  fi
done <<< "$raw"

exit 0
