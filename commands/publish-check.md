---
description: Pre-publish readiness review for a tool — stops before any remote create/push/publish
argument-hint: [project-path]
---

Do a pre-publish readiness review of the project at $ARGUMENTS (default: the current
working directory). This is a public release on my personal GitHub (Comradery64) plus the
appropriate package registry (npm for Node, etc.). Investigate the real repo state — don't
assume. STOP before any outward-facing action: do NOT create a remote, push, or publish.
Do the local prep, then hand me the exact commands to run myself.

Tick every box and report pass/fail with evidence:

1. SECRET & LEAK SCAN (highest priority): grep the publishable surface (exclude
   node_modules/dist/build artifacts) for private keys, tokens, real project/account IDs,
   internal hostnames, org names, and personal emails. Report filenames only — never print
   secret values. Confirm nothing engagement-specific leaked into shipped files.
2. IGNORE RULES: the ignore file blocks credentials, *.key/secret files, .env, build
   output, dependencies. After staging, confirm none of those are actually staged.
3. LICENSE & ATTRIBUTION: LICENSE present and matches the manifest's license field. If the
   work is derived/inspired by another project, include a NOTICE and verify the wording is
   accurate (reimplemented vs. copied).
4. DOCS ACCURACY: README install/usage matches the real distribution channel (e.g. `npx`
   only works if published to npm). No stale commands. Limitations/caveats documented.
5. PACKAGE METADATA: name, version, description, author, repository, homepage, bugs,
   license, engines, files/bin/exports (or language equivalent) present and correct. Check
   the registry name is available.
6. QUALITY GATES: typecheck/lint, tests, and build all green. Flag any coverage gaps.
7. CI: workflow present; all third-party actions pinned by full commit SHA (not tags);
   least-privilege `permissions:`.
8. GIT HYGIENE: clean tree; sensible conventional first commit; privacy-preserving commit
   identity (handle + noreply email, no real name/email leak, no AI attribution).
9. DECISIONS TO CONFIRM WITH ME before I push: target (public GitHub / registry / private),
   repo name, visibility, account.

Follow my global conventions throughout (no secrets in transcript or commits, SHA-pinned
actions, least privilege, no AI attribution, confirm before irreversible/outward-facing
steps).
