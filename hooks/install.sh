#!/bin/sh
# install.sh : point this machine's git at the shared hooks directory.
#
#   sh hooks/install.sh              install
#   sh hooks/install.sh --uninstall  remove
#
# This sets core.hooksPath globally, so the guard applies to every repository
# on this machine including ones cloned later. That same setting means git
# stops running each repository's own .git/hooks; the guard chains to a local
# pre-push itself, but any other local hook type would need the same treatment.
set -eu

HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "${1:-}" = "--uninstall" ]; then
  current=$(git config --global core.hooksPath 2>/dev/null || echo "")
  if [ "$current" = "$HOOKS_DIR" ]; then
    git config --global --unset core.hooksPath
    echo "removed: core.hooksPath"
  else
    echo "not installed here (core.hooksPath is ${current:-unset}); left alone"
  fi
  exit 0
fi

existing=$(git config --global core.hooksPath 2>/dev/null || echo "")
if [ -n "$existing" ] && [ "$existing" != "$HOOKS_DIR" ]; then
  echo "core.hooksPath is already set to: $existing" >&2
  echo "Refusing to replace it. Merge the two hook directories by hand." >&2
  exit 1
fi

git config --global core.hooksPath "$HOOKS_DIR"
echo "core.hooksPath -> $HOOKS_DIR"
echo ""
echo "Active in every repository on this machine. Verify now:"
echo "  sh $HOOKS_DIR/test-guard.sh"
