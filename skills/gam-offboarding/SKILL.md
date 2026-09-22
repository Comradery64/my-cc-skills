---
name: gam-offboarding
description: Google Workspace employee offboarding via GAM7 — suspend, deprovision, transfer data, archive. Use when offboarding, terminating, or deprovisioning a departing employee; when asked to remove someone's access, archive an account, transfer a leaver's Drive/Calendar/mail, or clean up a former employee. Trigger phrases include "offboard", "offboarding", "employee left", "terminate account", "departing", "leaver", "remove access", "archive user", "deprovision user", "delete user", "transfer their files".
---

# Google Workspace Offboarding (GAM7)

## Tenant Context

- GAM7 at `~/bin/gam7/gam`, authorized to `example.com` (customer `C01a2b3c4`)
- Licenses: **Google Workspace Enterprise Standard** (`1010020026`) + **Archived User** (`1010340004`)
- Archived User licenses ARE available — archiving is the correct terminal state, not deletion
- 2SV enrollment is 100% across active users
- **The `manager` / `relations` field is unpopulated — re-verified 2026-09-18: 0 of 82 users.**
  (Was 0 of 78 on 2026-09-15; headcount grew, coverage did not.) There is no org chart in the
  directory, so data-custodian routing cannot be resolved automatically. Ask a human for the
  recipient — every transfer so far has used an operator-chosen custodian, not a derived one.
  Deferred by the account owner 2026-09-18; revisit before automating Phase 3.

## Critical Rules

### NEVER delete. Archive.
Deletion destroys the archive and orphans Drive data. The terminal state is
`suspended=True archived=True`. Delete only after a retention period has demonstrably expired, and
only with explicit human approval on the specific account.

### Deletion has a 20-day undo — use it
`gam undelete user <email>` restores the account, its Drive files, and its group memberships.
After ~20 days it is unrecoverable, including via Google support. If you find an account was
deleted without a data transfer, **undelete immediately** — the clock is the only thing that matters.
`gam print users deleted_only fields primaryEmail,deletionTime` lists what is still restorable.

### Data transfer happens BEFORE any terminal action
`gam print datatransfers` shows what has actually been transferred. Zero records means nothing was
transferred, regardless of what anyone believes happened.

### NEVER print backup codes
`gam user <u> show backupcodes` and `print backupcodes` emit live 2SV-bypass credentials to stdout.
To check presence, count without printing:
`gam user <u> show backupcodes 2>/dev/null | grep -ci 'backup code'`

### No password reset is needed
Suspension blocks login outright. Do not use `password random` — it generates a secret that would
land in the transcript, and it buys nothing over suspension.

## Order of Operations (order is load-bearing)

### Phase 0 — Inventory (read-only, MANDATORY)
Record everything before mutating. Group memberships in particular cannot be reconstructed after
removal.

```bash
gam info user <u>                                  # roles, OU, aliases
gam print groups member <u>                        # ← WRITE THIS TO A DURABLE FILE
gam print admins user <u>                          # never offboard an admin unnoticed
gam user <u> print filelist fields id,name,owners  # what needs transferring
gam user <u> print tokens                          # OAuth grants = the downstream SSO checklist
gam print devices query "email:<u>" \
  fields deviceid,model,devicetype,osversion,managementstate,ownertype,lastsynctime
gam user <u> show forwards; gam user <u> show delegates; gam user <u> show sendas
```

**Write to `~/Dev/Work/Security/offboarding/offboard-record-<YYYY-MM-DD>.txt`** — a real file with
restore commands, never `/tmp`. Use that exact path so records accumulate in one place; they were
previously scattered under incident folders, which is why the Aug 2026 offboardings had no record
at all.

> ⚠️ **Phase 0 is the only phase that cannot be done late.** morgan.lee and casey.reyes were
> offboarded in Aug 2026 with no inventory captured. Both read 0 groups today — but whether they
> ever held `devadmin-aws` / `engineers-aws` / `platform-infra` is now **permanently unknowable**.
> Every other gap in that pair was remediable a month later; this one was not. If you are tempted to
> skip a phase under time pressure, skip a later one.

### Phase 1 — Deprovision + signout (do NOT suspend yet)
**`deprovision` cannot remove backup codes from a suspended account.** GAM fails with
`Backup Verification Codes Not Deprovisioned: User is suspended. You must unsuspend to process
backupcodes`. Suspending first silently leaves live 2SV-bypass codes on the account.

```bash
gam user <u> deprovision      # tokens, app-specific passwords, backup codes — DO THIS FIRST
gam user <u> signout          # kill live sessions
```

This already cuts Google-side access. Suspension is deliberately deferred to Phase 4 — see below.

Do NOT pass `turnoff2sv` to deprovision.

If an account is already suspended and needs deprovisioning, cycle it:
`suspended off` → `deprovision` → `suspended on`.

> ✅ **MEASURED 2026-09-16 — do NOT cycle just to revoke OAuth grants.**
> `gam user <u> delete token clientid <id>` **succeeds on an account that is both suspended AND
> archived.** Verified on morgan.lee (1 grant) and casey.reyes (7 grants) — all revoked to 0
> with no unsuspend, no unarchive, no login window ever opened.
>
> Reserve the `suspended off` cycle for **backup codes only** — that is the one artifact
> `deprovision` genuinely cannot touch while suspended. Count them first
> (`show backupcodes 2>/dev/null | grep -ci 'backup code'`); if the count is 0, the cycle buys
> nothing and only creates risk.
>
> Revoke per-grant rather than calling `deprovision` on a suspended account, so a backup-code
> failure cannot abort the token removal:
> ```bash
> gam user <u> print tokens 2>/dev/null | python3 -c "
> import csv,sys
> for r in csv.DictReader(sys.stdin): print(r['clientId'])
> " | while read -r cid; do gam user <u> delete token clientid \"$cid\"; done
> ```

### Phase 2 — Remove group memberships (this is the downstream deprovisioning step)
**Google Groups are the authorization plane for systems outside Workspace.** Removing membership
is not cleanup — it is the action that deprovisions the downstream account.

> 🚨 **MEASURED 2026-09-18 — for AWS Identity Center this is FALSE. Group removal does NOT revoke.**
> The clean test the note below called for was finally run: riley.chen (**ACTIVE** in Google, no
> permission set bound to the group, so zero blast radius) was removed from
> `agentserver-ops-aws@example.com`. Identity Center group membership was polled for **21 minutes**
> and never changed — still 1 member throughout.
>
> Contrast with the same connector's other behaviours:
>
> | Event in Google | Propagates to Identity Center? |
> |---|---|
> | User suspended / deleted | ✅ ~2 min → `UserStatus: DISABLED` |
> | Member ADDED to a group | ✅ observed (all 3 new groups synced with members) |
> | Member REMOVED from a group | ❌ **not within 21 min** |
>
> **Operational consequence: the thing that actually revokes AWS access is SUSPENDING THE GOOGLE
> ACCOUNT, not removing the group.** Phase 2 is still worth doing — it is correct hygiene, and it
> matters for other connectors like 1Password — but do NOT treat it as the revocation step for AWS,
> and never report AWS access as revoked on the strength of a group removal. Verify `UserStatus` in
> Identity Center instead.
>
> Unresolved: whether a slower periodic full sync eventually reconciles the removal. 21 minutes is
> the measured lower bound; the membership was restored after the test, so a longer observation
> would need a fresh run. Either way the operational rule stands — it is not timely enough to rely on.

Confirmed group-driven at the org:

| System | Mechanism |
|---|---|
| AWS IAM Identity Center | event-driven Google connector (`ssosync` retired at GATE 4) |
| 1Password | SCIM bridge (`k3s/apps/onepassword-scim-bridge` in internal-infra) |

Security-relevant groups seen so far: `devadmin-aws`, `engineers-aws`, `platform-infra`.

```bash
gam update group <g> remove member <u>   # per RECORDED group — safer than `delete groups`
```

**Run this while the account is still active (before Phase 4).** A connector that stops syncing
suspended or archived accounts would never observe the membership-removal event, leaving a live
downstream entitlement attached to a dead Google identity.

> ⚠️ **MEASURED 2026-09-14/15 — the connector disables promptly but leaves the record stale.**
>
> What the SCIM connector DID do: jordan.taylor was deleted in Google at 19:23:21Z; Identity Center set
> `UserStatus: DISABLED` at **19:25:05Z — about 2 minutes later.** Genuinely event-driven and fast.
> **A DISABLED Identity Center user cannot authenticate or assume any permission set**, so this is
> not a live access path.
>
> What it did NOT do: remove group memberships. jordan.taylor still shows `DevAdmin-AWS` +
> `Engineers-AWS` (granting `DevAdmin`/`PowerUser` on `111111111111`, `ReadOnly` on two more) — and
> `UpdatedAt` has been frozen at 19:25:05Z ever since. No further sync on the subsequent undelete,
> nor on the Google group removal. The record stops tracking Google once disabled.
>
> **Consequence: stale entitlements survive, inert, behind the DISABLED flag.** Re-enabling such a
> user — or any process that flips status back — restores live admin access without anyone
> re-granting it.
>
> **Still untested:** whether group removal alone propagates. The deletion had already disabled the
> user before we removed the groups, so this run cannot answer it. A clean test needs a user removed
> from a group while still ACTIVE in Google.
>
> Operational rule regardless: **verify downstream explicitly; never infer it** — and check
> `UserStatus`, not just presence. Presence alone says nothing about access in either direction.

#### AWS Identity Center verification (region-scoped — Identity Center lives in ONE region)
```bash
# instance + store id — MUST pass --region or list-instances returns []
aws sso-admin list-instances --profile identity-admin --region us-east-1

# is the user still present?
aws identitystore list-users --profile identity-admin --region us-east-1 \
  --identity-store-id d-9012345678 \
  --filters AttributePath=UserName,AttributeValue=<u>@example.com --query 'length(Users)'

# presence is not access — check group memberships
aws identitystore list-group-memberships-for-member --profile identity-admin --region us-east-1 \
  --identity-store-id d-9012345678 --member-id "UserId=<id>"
```
Gotchas: no default AWS profile is configured (`AWS_PROFILE` unset), so always pass
`--profile identity-admin`. In zsh, never assign to `UID` — it is a special integer variable and
a string assignment fails with `bad math expression`.

> 🚨 **MEASURED 2026-09-16 — group hygiene is NOT sufficient. Check DIRECT user assignments.**
> jordan.taylor held a **direct USER account assignment** (`ReadOnly` on the **management account**
> `333333333333`) alongside his group-derived access. SCIM syncs users and group memberships; it
> does **not** manage account assignments. So a direct assignment survives Google group removal,
> Google suspension, Google deletion — everything. Group-based offboarding will never find it.
>
> Enumerate BOTH principal types, per user:
> ```bash
> aws sso-admin list-account-assignments-for-principal --profile identity-admin --region us-east-1 \
>   --instance-arn <instanceArn> --principal-id <userId> --principal-type USER
> ```
> The response mixes `PrincipalType: USER` and `PrincipalType: GROUP` rows — the USER rows are the
> ones nothing upstream will clean up.

> 🚨 **Deleting the Identity Center user does NOT delete its account assignments.**
> After `aws identitystore delete-user` removed jordan.taylor (verified: 0 in the store, control user
> still present), the direct assignment was **still listed**, now pointing at a principal ID that no
> longer exists. An orphaned assignment is worse than a visible one: it does not appear in
> user-keyed access reviews, but it still sits in the assignment table.
>
> **Delete the assignment FIRST, then the user.** Verify with `list-account-assignments` scoped to
> the account + permission set, not with a user lookup.

> ⚠️ **Identity Center writes need the management-account profile.**
> `--profile identity-admin` resolves to `AWSReservedSSO_DevOpsLead` in `222222222222` and is
> effectively **read-only** — `sso:DeleteAccountAssignment` returns `AccessDeniedException`.
> Use **`--profile mgmt-admin`** (account `333333333333`) for assignment deletions. Reads are fine
> under `identity-admin`. Note `identitystore delete-user` DID succeed under `identity-admin`, so
> the two APIs have different permission boundaries — do not infer one from the other.

### Phase 3 — Data preservation
Skip only when the data is genuinely being retired; archiving retains it for Vault regardless.

```bash
gam create datatransfer <u> gdrive <recipient> privacy_level shared,private
gam create datatransfer <u> calendar <recipient> release_resources
gam user <u> delegate to <recipient>
gam user <u> forward on <recipient> keep
gam user <u> vacation on subject "..." message "..."
```

Archived data is reachable via Vault search/eDiscovery, NOT for day-to-day use. If someone has an
active dependency on a specific file, transfer that file explicitly.

> ⚠️ **An ARCHIVED account has no Calendar service — Phase 3 is not retroactive.**
> Measured 2026-09-16 on both morgan.lee and casey.reyes: any Calendar read or transfer returns
> `Calendar Service/App not enabled`. Drive still responds (`filelist`, `drivesettings` both work),
> but Calendar is gone. Recovering it requires `gam update user <u> archived off` first, which
> consumes an Enterprise Standard seat — check purchased-vs-assigned headroom before doing it, or
> the unarchive can trigger an auto-purchase.
>
> The account can stay **suspended** throughout that unarchive, so this does not open a login
> window. But the real lesson is ordering: **run Phase 3 before Phase 4, or lose the option.**
> Calendar `release_resources` is the step that frees meeting rooms held by recurring events —
> skipping it leaves rooms booked by a dead identity indefinitely.

### Phase 3.5 — Devices (MANDATORY — always account-wipe corporate data)

**Always attempt an account wipe on every registered device.** This removes corporate account data
while leaving personal data on the machine. Never `wipe device` — that is a FULL DEVICE WIPE and is
never appropriate for BYOD.

```bash
gam print devices query "email:<u>" \
  fields deviceid,model,devicetype,osversion,managementstate,ownertype,lastsynctime

gam wipe deviceuser "devices/<devId>/deviceUsers/<duId>" doit   # ← ALWAYS TRY THIS FIRST
```

> ⚠️ **MEASURED 2026-09-16 — the discriminator is DEVICE TYPE, not ownership.**
> 15 devices across morgan.lee, casey.reyes and jordan.taylor. All BYOD. Result split cleanly:
>
> | Device type | `wipe deviceuser` | Outcome |
> |---|---|---|
> | **IOS** (3/3) | ✅ `Wiped` | record moves to `managementState: WIPED` — corporate data actually removed |
> | **MAC_OS** (12/12) | ❌ `Precondition check failed` | Endpoint Verification only; no mobile management to satisfy the precondition |
>
> **Do not write this off as "BYOD can't be wiped" — iOS BYOD wipes fine.** macOS is the exception,
> because those records come from Endpoint Verification rather than Google mobile management.
>
> Other actions:
> - `block deviceuser` ❌ `The caller does not have permission` — GAM's grant lacks
>   `cloud-identity.devices`.
> - `delete deviceuser` ✅ succeeds; cascades and removes the parent device record too.
>
> **Procedure:** always issue the wipe first. Leave successfully-wiped records in `WIPED` — that is
> a terminal non-access state and it preserves the audit trail; deleting them destroys the evidence
> that the wipe happened. Only for devices where the wipe FAILED, fall back to `delete deviceuser`,
> then confirm nothing remains in `APPROVED`.
>
> To make macOS wipeable, grant GAM `cloud-identity.devices` and move the fleet to advanced
> management. Until then, deletion is the only lever there.

> 🚨 **`done: True` is NOT proof. Device ops are async long-running operations.**
> All 5 deletions returned `done: True` immediately while the records were still present and still
> `APPROVED` on the very next read. They only disappeared on a re-check ~45s later. Always sleep and
> re-verify to a count of 0 — never report a device removed on the strength of the return value.

### Phase 4 — Suspend + archive (terminal state)
Only after group removal has propagated downstream.

```bash
gam update user <u> ou /Deactivated
gam update user <u> recoveryemail "" recoveryphone ""
gam update user <u> suspended on
gam update user <u> archived on
```

> ⚠️ **The OU is `/Deactivated`. There is NO `/Offboarded` OU in customer `C01a2b3c4`** — this skill
> specified one that does not exist, so the command failed silently-ish for every prior run. As of
> 2026-09-16, `/Deactivated` held **0 users**: no offboarded account had ever been moved out of its
> team OU. Confirm the target OU exists with `gam print ous` before relying on it.

### Phase 5 — Verify (Workspace AND downstream)

Every line must reach its expected value. A step you ran is not a step that worked.

```bash
gam print users query "email=<u>" \
  fields primaryEmail,orgUnitPath,suspended,archived,recoveryEmail,recoveryPhone
                                  # expect /Deactivated, True, True, empty, empty
gam print groups member <u>       # expect 0
gam user <u> print tokens         # expect 0
gam user <u> show backupcodes 2>/dev/null | grep -ci 'backup code'   # expect 0
gam user <u> show asps            # expect 0
gam print devices query "email:<u>" fields deviceid,devicetype
                                  # expect 0 APPROVED; WIPED records may legitimately remain
gam print admins user <u>         # expect 0
gam print datatransfers           # confirm transfers actually ran
```

Workspace-side verification is not sufficient. Confirm the downstream systems too — AWS Identity
Center and 1Password — or the whole point of Phase 2 is unproven.

**Mandatory downstream check — direct AWS account assignments.** Group removal cannot reach these.
Run `list-account-assignments-for-principal` with `--principal-type USER` and confirm zero rows
come back with `PrincipalType: USER`. As of the 2026-09-16 audit, **4 people hold direct
assignments** (`IdentityCenterAdmin` ×2 and `RoleAdministrator` on the management account,
`AgentServerOps` on `111111111111`). If the leaver is one of them, Phase 2 will silently do nothing
and you must delete the assignment by hand — **assignment first, then the Identity Center user.**

**Always run a positive control alongside every downstream absence check.** "User not found" and
"my query/filter/credentials are broken" look identical. Probe a known-active account in the same
command; if the control does not come back present, the absence result is meaningless. A filtered
`list-users` that silently returns `[]` will otherwise read as a clean offboarding.

> **Mosyle MDM is an unclosed downstream.** Both users held a `Mosyle Business` OAuth grant, which
> means a Mosyle account almost certainly exists for each. Revoking the Google grant only stops
> Sign-in-with-Google; it does not deprovision the Mosyle account. There are no Mosyle API
> credentials wired into this runbook yet, so it currently cannot be verified — treat it as an open
> item on every offboarding until that changes. See the `mosyle-mdm` skill.
>
> More generally: surviving OAuth grants are a **map of the third-party SSO surface**.
> casey.reyes's 7 grants named GitHub, Slack, Tailscale, CoderPad, Greenhouse and Claude. Each is
> a separate system that Google suspension does not touch. Enumerate grants in Phase 0 and treat the
> list as the downstream checklist — see the `sso-dependency-audit` skill.

## Security-Relevant Memberships

Groups can gate access **outside** Workspace. At the org, `devadmin-aws` and `engineers-aws` feed
AWS access, and `platform-infra` gates infrastructure. Flag these explicitly in Phase 0 and confirm
what consumes them downstream before removal — Workspace suspension does not necessarily revoke
what a group membership grants elsewhere.

## GAM Gotchas (learned the hard way)

- **`gam print filelist query "..."` silently prepends `'me' in owners`** — it only searches OWNED
  files. Use `fullquery` for shared files. stderr echoes the effective query; read it to confirm.
- **`gam print users` expands fields** — requesting `suspended` yields
  `suspended,suspensionReason,suspensionTime`. Positional parsing breaks. Always use
  `csv.DictReader` and address columns by name.
- **`gam print users query "isArchived=true"` is unreliable** — it returned 2 of 4 genuinely
  archived accounts. Read the `archived` / `archivalTime` fields directly instead.
- **`archived=True` and "holds an Archived User license" are different states.** An account can be
  flagged archived without consuming an AU license. Check both.
- **`gam report token` is enormous** — ~48k rows per user per 6 months. Always scope with
  `user <email>` and filter by event name.
- **Device commands need the FULL resource name, not the bare deviceId.**
  `gam info device 615afb08-...` → `Request contains an invalid argument`. Use
  `devices/EiQ2MTVh...%3D` (the `name` column, `%3D` and all) and
  `devices/<name>/deviceUsers/<duId>` for deviceuser ops. Quote it — it contains `%`.
- **`gam wipe deviceuser` ≠ `gam wipe device`.** The first is an account wipe (corporate data only);
  the second wipes the entire machine. Never run the second on BYOD.
- **Device ops return `done: True` before they have taken effect** — async LROs. Sleep ~45s and
  re-verify to a count of 0.
- **`gam update user` returns `Updated` before the change is readable.** Measured on jordan.taylor: an
  OU move to `/Deactivated` and a `recoveryemail ""` clear both reported `Updated` while the very
  next read still showed `/` and the old Gmail address. The phone cleared immediately, the email did
  not — so fields within one call converge at different rates. Re-read after ~40s, and confirm from
  two sources (`print users` *and* `info user`) before calling a Phase 4 field done.
- **Recovery email/phone are a live account-recovery path and are NOT cleared by suspension.**
  jordan.taylor sat suspended+archived for a day with `jtaylor88@gmail.com` and a personal mobile
  still attached. Always clear them explicitly and verify.
- **`gam print users query "orgUnitPath='/X'"` needs the inner quotes** — and returns 0 rows rather
  than erroring when the OU does not exist, so a typo'd OU looks like an empty OU.
- Zsh: never combine `2>&1` with a stdout redirect (MULTIOS tees). Use `cmd 2>/tmp/err >/dev/null`.

## Meta-rule: verify by executing

Three of this skill's own instructions were wrong until they were run: the `/Offboarded` OU never
existed, the suspend-cycle for token revocation was unnecessary, and the account-wipe it now
mandates is a guaranteed no-op on macOS BYOD. None of that was visible by reading. Run the command,
check the resulting state, and write the measured result back into this file with a date.

## Roadmap

Short term this skill is the runbook. Long term, offboarding moves to an **Ashby (HR) → Temporal**
workflow.

**Temporal lives in `peopleops-infra`, NOT `internal-infra`/Networking.**
- `infra/terraform/modules/temporal/main.tf` — official Temporal Helm chart + CloudNativePG
  Postgres (HA; replaced a single-instance Bitnami chart with no failover)
- `services/interview-notifier/` — an existing, working Temporal service to copy. Layout:
  `clients/` (external APIs), `workflows/` (`reconcile.py` poller + per-entity lifecycle),
  `activities/`, plus `worker.py`, `config.py`, `models.py`
- Its pattern — poll HR every 2 min on an `updated_at` watermark, `signal_with_start` a per-entity
  workflow with durable timers — maps directly onto offboarding
- NOTE: interview-notifier still targets the **Greenhouse** Harvest API, while Ashby was granted
  to all 76 users on 2026-09-01. A Greenhouse → Ashby migration is in flight; decide whether
  offboarding targets Ashby directly or waits behind it.

When building that:

- Each phase above maps to a Temporal activity; the ordering constraints become workflow
  dependencies, not comments. Phase 1's deprovision-before-suspend is a real edge, not a preference.
- Ashby termination events are the trigger; Temporal owns retries and the multi-day waits
  (retention period before any deletion decision).
- **Populate the Workspace `manager` field first** — `gam update user <u> relation manager <email>`.
  Custodian routing needs a source of truth, and today there is none. Treat "no manager set" as a
  hard failure that blocks the workflow rather than a step the automation skips.
- Keep deletion out of the automation entirely, or behind a human approval activity.
