---
name: gyb-archive-to-group
description: Archive a departing/offboarded Google Workspace user's Gmail by backing it up with GYB (Got Your Back) and restoring it into a Google Group of the freed-up name, then suspending the old account. Use this whenever someone needs to offboard, archive, preserve, or "back up and move" a Workspace user's mailbox — e.g. "back up a shared account and turn it into a group", "archive a departing employee's email", "we're renaming this account and want the old mail kept somewhere", "preserve so-and-so's inbox before we delete their account", or any GYB backup/restore-to-group task. Also use for plain GYB mailbox backups and for first-time GYB project/service-account setup. Trigger even if the user doesn't say "GYB" — the giveaway is wanting to keep a user's email after they leave or after a rename.
---

# GYB: Archive a Mailbox into a Google Group

This skill captures the full offboarding flow: **back up** a user's Gmail with GYB,
**rename** the account to free its address, **create a Google Group** at that
address, **restore** the mail into the group's archive, then **suspend** the old
account. It also covers plain backups and the one-time GYB setup.

The whole point is preserving a departed person's mail somewhere searchable and
access-controlled, without keeping a paid, sign-in-capable user account around.

## Environment (fill in for your org)

These are placeholders — replace with your org's actual values, and verify they
still hold before relying on them.

- **GYB binary:** `~/bin/gyb/gyb` (PyInstaller build). The credential files
  (`oauth2service.json`, `client_secrets.json`) live in that same folder — GYB
  looks for them next to the executable.
- **Backups live in:** `~/gyb-backups/` — run GYB from there so backup folders
  land in one place.
- **Workspace admin / `--use-admin`:** a super admin account in your domain, e.g.
  `admin@example.com`.
- **GCP org ID:** your numeric GCP organization ID (relevant only for first-time
  setup — see `references/project-setup.md`).
- **Service account DwD scopes authorized:** `https://mail.google.com/`,
  `apps.groups.migration`, `drive.appdata`, `userinfo.email`. DwD is domain-wide, so
  once authorized it works for any user in the domain.

## The one rule that prevents most pain

**`backup` and `restore-group` use `--service-account` and are fully
non-interactive — run them directly (background is fine).** Anything that does an
**OAuth browser flow** (`create-project`, or any command *without*
`--service-account`) is **interactive and will crash with `EOFError` if run through
a non-interactive shell** (including an `!`-prefix in-session shell in an agent
harness). Those must be run by the user in a real Terminal. When in doubt: SA
actions = you can run them; OAuth actions = hand to the user.

## Pre-flight (always do this first)

1. **Confirm the GYB binary runs** and credentials are present:
   ```bash
   ~/bin/gyb/gyb --version
   ls ~/bin/gyb/oauth2service.json ~/bin/gyb/client_secrets.json
   ```
   If `--version` exits 137 (SIGKILL) or errors on `httplib2`/cacerts, see
   `references/troubleshooting.md`. If credentials are missing, do one-time setup
   first (`references/project-setup.md`).

2. **Confirm service-account DwD works for the *target* user** (catches renamed /
   suspended / nonexistent accounts before you waste time):
   ```bash
   ~/bin/gyb/gyb --action check-service-account --email <target>
   ```
   All four scopes should say `PASS`. A `FAIL` / `unauthorized_client` usually means
   the address doesn't resolve (renamed?), the user is suspended, or scopes aren't
   propagated yet — see troubleshooting.

## Workflow

Work through these in order. **Sequencing matters**: back up while the account is
still active, and you can't create a group at an address while a user still owns it
— so rename comes between backup and group creation.

### 1. Estimate (sanity check + size)

```bash
cd ~/gyb-backups
~/bin/gyb/gyb --action estimate --email <target> --service-account
```
Tells you message count and total size, and proves SA auth works for this user
before committing to a full run. Confirm there's enough free disk (`df -h`).

### 2. Back up

```bash
cd ~/gyb-backups
~/bin/gyb/gyb --action backup --email <target> --service-account
```
Creates `GYB-GMail-Backup-<target>/`. Non-interactive; for large mailboxes run it in
the background and monitor. Resumable — re-running skips already-backed-up messages.

### 3. Verify the backup (do not skip)

Before touching the live account, confirm the backup is complete and intact:
```bash
scripts/verify_backup.sh "~/gyb-backups/GYB-GMail-Backup-<target>"
```
This checks that on-disk `.eml` count == DB row count, flags any zero-byte messages,
and reports labels captured. If it doesn't reconcile, re-run the backup before
proceeding — everything downstream is destructive-ish (rename, suspend).

**Tell the user the verified counts and get their go-ahead before step 4.** Steps 4+
change live accounts.

### 4. Rename the source account — *user action, admin console*

The user renames `<target>` (e.g. a shared mailbox address) to an archival name
(e.g. the same address with `-old` appended) in **admin.google.com → Directory →
Users → user → Rename**. This frees the original address so a group can take it.
The mailbox data follows the renamed account.

After this, the **target for backup/restore is the new (renamed) name**, but the
**group** gets the **original** name. Keep these straight.

> If the user already renamed before backing up (common mistake), just back up the
> *new* address — the data is the same account.

### 5. Create the destination Google Group — *user action, admin console*

User creates the group at the **original** address in
**admin.google.com → Directory → Groups → Create**:
- **Email:** the original address.
- **⚠️ Conversation history = ON.** The Groups Migration API only stores restored
  messages where history/archiving is enabled. Without it the import has nowhere to
  land.
- **🔒 Lock it down.** This is someone's personal mail going into a shared archive.
  Restrict "who can view conversations" to the specific people who should see it, and
  restrict membership. Flag this to the user explicitly — it's a privacy matter.

Give it a couple of minutes to propagate.

### 6. Restore into the group

```bash
cd ~/gyb-backups
~/bin/gyb/gyb --action restore-group \
  --email <ORIGINAL address / the group> \
  --use-admin admin@example.com \
  --local-folder "~/gyb-backups/GYB-GMail-Backup-<renamed target>" \
  --service-account
```
**Critical argument semantics** (easy to get wrong):
- `--email` is the **target group address** (GYB passes it as `groupId`), *not* the
  mailbox you backed up.
- `--local-folder` is the **backup folder** (named after the renamed mailbox).
- `--use-admin` is the admin GYB authenticates as for the Groups Migration API.

Non-interactive. For 100s–1000s of messages, run in the background. Per-message
errors are soft (it continues); messages over the group size limit (~25 MB) are
skipped and logged.

### 7. Verify the restore

```bash
# all messages tracked as restored?
sqlite3 "~/gyb-backups/GYB-GMail-Backup-<renamed target>/<group address>-restored.sqlite" \
  "SELECT COUNT(*) FROM restored_messages;"
# scan the run output for problems
grep -iE "error|skip|too large|unauthor|forbidden|quota" <restore output>
```
`restored_messages` should equal the backup's message count, with no error lines.
Then have the user spot-check **groups.google.com → the group → Conversations**
(allow a few minutes for the web view to populate). Note: a group is a flat,
threaded **conversation archive** — Gmail labels/folders are *not* recreated as such.
The local backup remains the only full-fidelity copy (messages + labels).

### 8. Suspend (not delete) the old account — *user action, admin console*

**admin.google.com → Directory → Users → `<renamed target>` → Suspend.** Suspend
rather than delete: it blocks sign-in and mail flow but **preserves the account and
data**, so if the archive turns out incomplete you can unsuspend and re-back-up. The
license stays consumed until the user later deletes it.

> You cannot suspend from here programmatically — it needs the Admin SDK
> `admin.directory.user` scope, which the GYB service account deliberately does not
> have (least privilege). Don't add directory-write power to the SA for a one-off;
> direct the user to the console.

### 9. Retain the local backup

Leave `GYB-GMail-Backup-<renamed target>/` in place unless told otherwise — it's the
highest-fidelity copy. Recommend the user store it somewhere durable (not just one
machine) and delete it only once they're confident the archive is sufficient.

## Secret hygiene

`oauth2service.json` contains the service-account **private key**. Never print its
contents. If you need fields from it, read only the non-secret ones, e.g.
`jq -r '.project_id, .client_email' oauth2service.json` — never `cat` it or echo the
`private_key`.

## When something breaks

See `references/troubleshooting.md` for the specific errors seen with this kind of
setup: `unauthorized_client`, OAuth `EOFError`, cacerts `RuntimeError`, code-signing
`Killed: 9` / exit 137, and the `disableServiceAccountKeyCreation` 400.

## First-time setup (no service account yet)

If `oauth2service.json` doesn't exist, the GCP project + service account + DwD must be
created first. This is a separate, mostly interactive procedure with an org-policy
gotcha. See `references/project-setup.md`.
