#!/usr/bin/env bash
# Verify the integrity of a GYB backup folder.
#
# Usage: verify_backup.sh /path/to/GYB-GMail-Backup-<email> [expected_count]
#
# Checks that the on-disk .eml files reconcile with the message DB, flags empty
# messages, and reports labels. Pass an optional expected message count (e.g. from
# `gyb --action estimate` / `count`) to assert against Gmail's own number.
#
# Exits 0 if everything reconciles, 1 otherwise. Prints a short report either way.

set -uo pipefail

BK="${1:-}"
EXPECTED="${2:-}"

if [[ -z "$BK" ]]; then
  echo "usage: verify_backup.sh <backup-folder> [expected_count]" >&2
  exit 2
fi
if [[ ! -d "$BK" ]]; then
  echo "ERROR: not a directory: $BK" >&2
  exit 2
fi

DB="$BK/msg-db.sqlite"
if [[ ! -f "$DB" ]]; then
  echo "ERROR: no msg-db.sqlite in $BK (not a GYB-format backup folder?)" >&2
  exit 2
fi

# DB row count
db_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM messages;" 2>/dev/null)
db_with_file=$(sqlite3 "$DB" "SELECT COUNT(*) FROM messages WHERE message_filename IS NOT NULL;" 2>/dev/null)
labels=$(sqlite3 "$DB" "SELECT COUNT(DISTINCT label) FROM labels;" 2>/dev/null)

# On-disk .eml files (stored under year/month/day subfolders)
eml_count=$(find "$BK" -type f -name "*.eml" 2>/dev/null | wc -l | tr -d ' ')
empty_count=$(find "$BK" -type f -name "*.eml" -size 0 2>/dev/null | wc -l | tr -d ' ')

total_size=$(du -sh "$BK" 2>/dev/null | cut -f1)

echo "GYB backup verification: $BK"
echo "  total size on disk : $total_size"
echo "  DB message rows    : $db_count"
echo "  DB rows w/ filename : $db_with_file"
echo "  .eml files on disk : $eml_count"
echo "  zero-byte .eml     : $empty_count"
echo "  distinct labels    : $labels"
[[ -n "$EXPECTED" ]] && echo "  expected (Gmail)   : $EXPECTED"

ok=0

if [[ "$db_count" != "$eml_count" ]]; then
  echo "FAIL: DB rows ($db_count) != .eml files ($eml_count). Re-run the backup."
  ok=1
fi
if [[ "$db_count" != "$db_with_file" ]]; then
  echo "FAIL: $((db_count - db_with_file)) DB rows have no filename. Re-run the backup."
  ok=1
fi
if [[ "$empty_count" != "0" ]]; then
  echo "FAIL: $empty_count zero-byte message file(s). Re-run the backup."
  ok=1
fi
if [[ -n "$EXPECTED" && "$EXPECTED" != "$db_count" ]]; then
  echo "FAIL: backup has $db_count messages but expected $EXPECTED. Re-run / investigate."
  ok=1
fi

if [[ "$ok" == "0" ]]; then
  echo "PASS: backup is complete and intact ($db_count messages)."
fi
exit $ok
