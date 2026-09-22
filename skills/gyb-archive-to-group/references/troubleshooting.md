# GYB Troubleshooting

Specific errors seen with a GYB service-account setup like the one this skill
describes, and what actually fixed them.

## `unauthorized_client` / a scope shows `FAIL`

```
google.auth.exceptions.RefreshError: ('unauthorized_client: Client is unauthorized
to retrieve access tokens using this method, or client not authorized for any of the
scopes requested.', ...)
```

The token exchange to impersonate the target user failed. Almost always one of:

1. **The address doesn't resolve** — the most common cause here. If the account was
   renamed (e.g. `shared@` → `shared-old@`), `shared@` no longer points at a mailbox.
   Target the **current** address. Diagnose by running
   `check-service-account --email <addr>` against both the old and new names.
2. **User suspended / Gmail disabled** for that user.
3. **DwD scopes not authorized or not yet propagated.** Re-run
   `check-service-account`; if scopes were just added in the admin console, wait a few
   minutes. Note DwD is domain-wide, so if it passes for one user it should pass for
   all — a single-user failure points at #1 or #2, not the scopes.

## OAuth flow crashes with `EOFError`

```
File "gyb.py", in _wait_for_user_input ... EOFError: EOF when reading a line
... KeyError: 'code'
```

GYB's OAuth (`create-project`, or any command without `--service-account`) is
**interactive** — it waits for a verification code/URL on stdin. It was run through a
non-interactive shell (e.g. an in-session `!`-prefix shell, a pipe, or a background
task), which delivers EOF. **Fix:** have the user run it in a real Terminal window. It
crashes *before* creating anything, so nothing to clean up (but check for orphaned
projects if it's `create-project` — see project-setup.md).

Backup/restore with `--service-account` are non-interactive and safe to run anywhere.

## `HTTPLIB2_CA_CERTS not a valid file` (rebuilt binary only)

```
RuntimeError: Environment variable HTTPLIB2_CA_CERTS not a valid file
  httplib2/certs.py ... where()
```

`gyb.py` sets `HTTPLIB2_CA_CERTS='cacerts.pem'` (a **relative** path) before importing
httplib2. Recent httplib2 versions raise if that env var points at a non-existent file
(older versions silently fell back). A locally-rebuilt binary that pulled a newer
httplib2 via `pip` hits this; the official CI binary doesn't.

**Fix:** use the official prebuilt binary (keep a `gyb.pre-patch.bak` copy of the last
known-good one). If you must rebuild, pin an older httplib2 or change the cacerts
handling to an absolute (`_MEIPASS`-resolved) path. The local patch only improves
`create-project`'s error message, which you rarely re-run, so reverting to the
official binary for day-to-day backup/restore is the pragmatic call.

## `Killed: 9` / exit code 137 right at launch (macOS)

A freshly built or **copied** PyInstaller binary is killed by the kernel because its
ad-hoc code signature is invalid (copying a Mach-O can invalidate the signature on
Apple Silicon).

**Fix:** re-sign it ad-hoc:
```bash
codesign --force -s - ~/bin/gyb/gyb
~/bin/gyb/gyb --version   # should print and exit 0
```

## `create-project` returns a raw 400 about key creation

```
400 ... "Key creation is not allowed on this service account." FAILED_PRECONDITION
   constraints/iam.disableServiceAccountKeyCreation
```

The org policy blocks SA key creation. This is a first-time-setup issue — see
`references/project-setup.md` for the temporary org-policy disable / re-enable dance.
If you're on the patched `gyb.py`, it prints these instructions itself and exits 4
(and the installer scripts stop instead of looping).

## Backup/restore counts don't reconcile

- **Backup:** re-running `backup` is resumable and idempotent — it re-fetches only
  missing messages. If `verify_backup.sh` flags a mismatch, just run `backup` again.
- **Restore:** `restore-group` tracks progress in
  `<group-address>-restored.sqlite` inside the backup folder, so re-running resumes and
  won't duplicate. Use `--noresume` only if you deliberately want to start over.

## Restored messages don't appear in the group

- Confirm the group has **Conversation history = ON** (Groups settings). The Groups
  Migration API has nowhere to store messages otherwise.
- The web view (groups.google.com) can lag a few minutes after the import finishes.
- Messages over ~25 MB are skipped (logged in the run output) — check for "too large".
