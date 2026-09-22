# Repository conventions

This repository is public. So are several sibling repositories, including forks
of other people's work. These rules decide what is allowed to be tracked in one
and where everything else goes.

## Public by default

Assume every tracked file will be read by a stranger with no context about this
machine, this employer, or these clients. A file that only makes sense to
someone sitting at this desk does not belong in a tracked file.

## Two tiers of private

**Whole private files** are gitignored by name. Working notes and machine state:
`CLAUDE.md`, `PLAN.md`, `NOTES.md`, `memory/`, `.env`, local settings. These
never enter a commit at all.

**Local overlays** cover the harder case: a tracked file that is correct in
public, but where this machine needs extra specificity. The overlay lives beside
it as `LOCAL.md`, or as `<name>.local.md` when several sit in one directory, and
is gitignored everywhere.

```text
research/trap-build/README.md   tracked   "a headless browser CLI that exits
                                           nonzero on a failed assertion"
research/trap-build/LOCAL.md    ignored   "use dev-browser at ~/Library/pnpm/bin,
                                           QuickJS sandbox, daemon keeps state"
```

Add both patterns to every repository's ignore file:

```gitignore
# Local overlays: machine-specific detail that must never be published.
# A tracked file may point at one, but must stand alone without it.
LOCAL.md
*.local.md
```

## The rule that makes overlays safe

**A tracked file must stand alone.** An overlay may add specificity; it may
never carry required meaning. If deleting every `LOCAL.md` leaves a tracked
document incomplete, wrong, or unfollowable, the split is broken and the missing
part belongs in the tracked file, written generically.

The test is mechanical: read the tracked file as if the overlay does not exist.
Can a stranger act on it? If not, fix the tracked file.

## Write the property, not the product

Most of what feels machine-specific is really a missing specification. The
public instruction "install Playwright" dates immediately and hides what matters;
"a headless browser driven by a command that exits nonzero when an assertion
fails" is true forever and lets the reader use what they already have. Name the
property in the tracked file and the product in the overlay. The public document
usually gets better in the process, not more vague.

## Before pushing anything public

Run `/publish-check` (see `commands/publish-check.md`). Its secret and leak scan
covers credentials, real account ids, internal hostnames, and personal emails.
Add one check of your own for this convention: confirm no `LOCAL.md` or
`*.local.md` is staged, and that no tracked file names a path under `/Users/`.

```bash
git diff --cached --name-only | grep -E '(^|/)(LOCAL\.md|.*\.local\.md)$' && echo "BLOCKED: overlay staged"
git grep -n "/Users/" -- . ':!*.local.md' ':!LOCAL.md'
```

## Forks of other people's repositories

A fork is public and carries someone else's name in its history. Personal tool
choices and local paths do not belong in one at any price; they go in an
overlay. Keep `origin` pointed at the fork and give the parent remote a disabled
push URL so a stray `git push upstream` fails locally before it reaches the
network:

```bash
git remote set-url --push upstream DISABLED_pushes_to_upstream_are_blocked
```
