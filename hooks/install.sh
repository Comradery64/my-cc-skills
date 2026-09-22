#!/bin/sh
# install.sh : install the push guard for every repository on this machine.
#
#   sh hooks/install.sh              install or update
#   sh hooks/install.sh --uninstall  remove
#
# The hook is COPIED to ~/.config/git/hooks rather than run from this checkout.
# core.hooksPath pointing into a project directory fails open: move the project,
# rename it, or leave an external volume unmounted, and git finds no hooks and
# runs none, silently. A copy under the home directory is always present.
#
# The cost of a copy is drift. Re-run this after changing the hook; the
# installed file records which commit it came from.
set -eu

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/git/hooks"

if [ "${1:-}" = "--uninstall" ]; then
  current=$(git config --global core.hooksPath 2>/dev/null || echo "")
  [ "$current" = "$DEST_DIR" ] && git config --global --unset core.hooksPath && echo "unset core.hooksPath"
  rm -f "$DEST_DIR/pre-push"
  echo "removed $DEST_DIR/pre-push"
  exit 0
fi

existing=$(git config --global core.hooksPath 2>/dev/null || echo "")
if [ -n "$existing" ] && [ "$existing" != "$DEST_DIR" ]; then
  echo "core.hooksPath already points elsewhere: $existing" >&2
  echo "Refusing to replace it. Merge the two hook directories by hand." >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
origin=$(git -C "$SRC_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
{
  printf '# installed by my-cc-skills hooks/install.sh from commit %s\n' "$origin"
  printf '# edit the source, not this copy, then re-run the installer\n'
  tail -n +2 "$SRC_DIR/pre-push"
} > "$DEST_DIR/pre-push.tmp"
printf '%s\n' "#!/bin/sh" | cat - "$DEST_DIR/pre-push.tmp" > "$DEST_DIR/pre-push"
rm -f "$DEST_DIR/pre-push.tmp"
chmod +x "$DEST_DIR/pre-push"
git config --global core.hooksPath "$DEST_DIR"

echo "installed: $DEST_DIR/pre-push  (from $origin)"
echo "core.hooksPath -> $DEST_DIR"
echo ""
echo "Active in every repository on this machine, including future clones."
echo "Verify:  sh $SRC_DIR/test-guard.sh"
