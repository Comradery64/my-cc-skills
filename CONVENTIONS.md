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

## What this convention does not do

Read this before relying on any of it.

The overlay split removes one failure mode: there is a single copy of each
tracked document, so a public and a private version of the same prose cannot
drift apart. It removes nothing else. Nothing here prevents machine-specific
detail from being written into the tracked file in the first place.
`.gitignore` matches filenames; it cannot see content.

That gap matters more the less each commit is read. When most lines are written
by an agent and no human reviews every one, a convention stated only in prose is
not a control. It is a preference that holds until the first time something
writes to the wrong file, and that failure is silent and public.

So treat everything below as the intent, and put the enforcement somewhere that
fails closed: a pre-push check that refuses tracked content matching a private
pattern, and `/publish-check` before any deliberate publish. Where the content
is genuinely confidential rather than merely machine-specific, do not rely on
either — keep the source of truth in a private repository and publish outward
deliberately.

A pattern check catches path-shaped and name-shaped leaks. It cannot tell that a
paragraph describes a client's internal process. Only a human decision at
publish time catches that, which is the argument for private-first on anything
that carries real confidentiality.

## Which regime a repository gets

| Repository | Regime | Why |
|---|---|---|
| A fork of someone else's public repo | Overlay plus push guard | Already public; private-first is not available |
| Your own public collection, like this one | Private-first, publish deliberately | You control the boundary, so use it |
| Anything carrying client or employer detail | Private, no public counterpart | No convention is worth that risk |

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

## The push guard

`hooks/pre-push` refuses a push that adds a `/Users/<name>/` path, a
`<!-- local:start -->` fence, or a tracked `LOCAL.md` / `*.local.md`. Install it
once for the whole machine:

```bash
sh hooks/install.sh          # sets core.hooksPath globally
sh hooks/test-guard.sh       # 5 controls: 3 blocks, 1 clean push, 1 opt-out
```

Four properties worth knowing:

- It scans **only the lines a push adds**, so adopting it on an old repository
  never requires cleaning history first.
- `core.hooksPath` **replaces** `.git/hooks` for every repository. The guard
  chains to a repository-local `pre-push` so that one keeps working; any other
  local hook type would stop running.
- The installer **copies** the hook to `~/.config/git/hooks`. Pointing
  `core.hooksPath` at a project directory fails open: move or rename the
  project, or leave an external volume unmounted, and git finds no hooks and
  runs none without saying so. Re-run the installer after editing the hook; the
  installed copy records the commit it came from.
- Overrides are deliberate and visible: `git push --no-verify` for one push,
  `git config guard.disable true` for one repository.
- Run `test-guard.sh` after any change to it. A guard nobody has watched fail is
  not a guard, which is the same rule this collection applies to gate oracles.

## Forks of other people's repositories

A fork is public and carries someone else's name in its history. Personal tool
choices and local paths do not belong in one at any price; they go in an
overlay. Keep `origin` pointed at the fork and give the parent remote a disabled
push URL so a stray `git push upstream` fails locally before it reaches the
network:

```bash
git remote set-url --push upstream DISABLED_pushes_to_upstream_are_blocked
```
