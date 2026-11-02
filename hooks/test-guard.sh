#!/bin/sh
# test-guard.sh : prove the pre-push guard blocks and, just as importantly, that
# it lets ordinary work through. A guard nobody has watched fail is not a guard.
set -eu

HOOK="$(cd "$(dirname "$0")" && pwd)/pre-push"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
pass=0; fail=0

check() { # name expected_exit
  name="$1"; want="$2"
  got=0
  printf 'refs/heads/%s %s refs/heads/%s %s\n' "$BRANCH" "$(git -C "$WORK/local" rev-parse HEAD)" "$BRANCH" "$REMOTE_SHA" \
    | "$HOOK" origin "file://$WORK/remote" >/dev/null 2>&1 || got=$?
  if [ "$got" = "$want" ]; then pass=$((pass+1)); echo "ok   $name"
  else fail=$((fail+1)); echo "FAIL $name (exit $got, wanted $want)"; fi
}

git init -q --bare --template= "$WORK/remote"
git init -q --template= "$WORK/local"
cd "$WORK/local"
git config user.email t@example.invalid; git config user.name t
git remote add origin "file://$WORK/remote"
echo "generic instructions" > README.md
git add README.md && git commit -qm "base"
BRANCH=$(git symbolic-ref --short HEAD)
git push -q --no-verify origin "$BRANCH"
REMOTE_SHA=$(git rev-parse HEAD)

echo "clean push" > note.md
git add note.md && git commit -qm "clean"
check "a clean push is allowed" 0

printf 'run /%s/someone/bin/tool\n' Users >> README.md
git add README.md && git commit -qm "leak a home path"
check "an added /Users/ path is blocked" 1

git reset -q --hard "$REMOTE_SHA"
printf '<!-- %s -->\nmachine notes\n' local:start > README.md
git add README.md && git commit -qm "leak a local fence"
check "an added local fence is blocked" 1

git reset -q --hard "$REMOTE_SHA"
echo "machine detail" > LOCAL.md
git add -f LOCAL.md && git commit -qm "commit an overlay file"
check "a committed LOCAL.md is blocked" 1

git reset -q --hard "$REMOTE_SHA"
printf 'run /%s/someone/bin/tool\n' Users >> README.md
git add README.md && git commit -qm "leak, but disabled"
git config guard.disable true
check "an explicit per-repo opt-out is honored" 0
git config --unset guard.disable

echo ""
echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
