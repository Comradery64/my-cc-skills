# One-Time GYB Project & Service Account Setup

Do this only when `oauth2service.json` doesn't already exist in the GYB folder. Once a
service account exists and DwD is authorized, you never repeat this — backups for any
user reuse the same service account (DwD is domain-wide).

This procedure is **mostly interactive** (browser OAuth) and **has a Google Cloud
org-policy gotcha** that will block it on orgs created since ~mid-2024. Read the whole
thing before starting.

## Overview

`gyb --action create-project` will:
1. Create a GCP project (`gyb-project-<random>`).
2. Enable the needed APIs.
3. Create a service account.
4. **Create + download a service-account key** → `oauth2service.json`.  ← the org policy blocks this step.

Then `gyb --action check-service-account` walks you through authorizing the
domain-wide-delegation (DwD) scopes in the Workspace admin console.

## The blocker: `iam.disableServiceAccountKeyCreation`

Many orgs enforce `constraints/iam.disableServiceAccountKeyCreation` (a
"secure-by-default" policy on by default for new GCP orgs). Step 4 fails with:

```
400 ... "Key creation is not allowed on this service account." FAILED_PRECONDITION
   constraints/iam.disableServiceAccountKeyCreation
```

Unpatched installer scripts then **loop forever, creating a new orphaned project each
retry**. (GYB's patched `gyb.py` — see the upstream PR / local repo — detects this and
exits cleanly with guidance instead.)

You must **temporarily relax the org policy**, create the project, then **re-secure**.

### Who can change the policy

Editing org policy needs `roles/orgpolicy.policyAdmin` at the org. Your Workspace
super admin may not have this by default — a super admin *can* grant themselves org
IAM roles via gcloud (implicit bootstrap) if no one else is available. Otherwise ask
whoever holds org-admin / policyAdmin in your org.

### Steps (run as your Workspace super admin; gcloud must be interactively authed)

If gcloud's token is stale: have the user run `! gcloud auth login` in-session.

```bash
ORG=<your-gcp-org-id>

# 1. Grant yourself policyAdmin (temporary, least-privilege).
gcloud organizations add-iam-policy-binding $ORG \
  --member="user:admin@example.com" --role="roles/orgpolicy.policyAdmin"

# 2. Disable enforcement (v1 resource-manager works; the v2 org-policies API may be
#    disabled on the active project — that's fine, ignore it).
gcloud resource-manager org-policies disable-enforce \
  constraints/iam.disableServiceAccountKeyCreation --organization=$ORG

# confirm not enforced (want booleanPolicy:{} / enforced:false), then wait ~1-2 min
gcloud resource-manager org-policies describe \
  constraints/iam.disableServiceAccountKeyCreation --organization=$ORG --effective
```

### Create the project — INTERACTIVE, real Terminal only

`create-project` does a browser OAuth flow. **Do not run it via an in-session `!`
shell** — it prompts for a verification code/URL and will crash with `EOFError` on a
non-interactive stdin. Have the user run, in Terminal.app:

```bash
~/bin/gyb/gyb --action create-project --email admin@example.com
```
Wait for **"That's it! Your GYB Project is created and ready to use."** It writes
`oauth2service.json` + `client_secrets.json` next to the binary.

### Re-secure immediately after success

```bash
gcloud resource-manager org-policies enable-enforce \
  constraints/iam.disableServiceAccountKeyCreation --organization=$ORG
gcloud organizations remove-iam-policy-binding $ORG \
  --member="user:admin@example.com" --role="roles/orgpolicy.policyAdmin"
```
The downloaded key keeps working after re-enabling — the policy only blocks creating
*new* keys.

### Clean up orphaned projects

Each failed/retried run may have left an empty `gyb-project-*`. The real one is the
project referenced by the new `oauth2service.json`:
```bash
jq -r '.project_id' ~/bin/gyb/oauth2service.json   # the keeper
gcloud projects list --filter="name:'Got Your Back Project'" # find all
gcloud projects delete <each-orphan> --quiet                  # delete the rest
```

## Authorize DwD scopes

```bash
~/bin/gyb/gyb --action check-service-account --email admin@example.com
```
It prints a client ID + scope list and a short link to the admin console with the
fields pre-filled (**admin.google.com → Security → API controls → Domain-wide
delegation**). The user clicks Authorize, waits a few minutes, then re-runs the
command until **all scopes PASS**. `check-service-account` does a real token exchange,
so PASS means it genuinely works.

DwD is domain-wide: once these scopes pass for one user, the service account can
impersonate **any** user in the domain for those scopes. You're now ready for the main
backup/restore workflow.

## macOS note: rebuilding the GYB binary

If you ever rebuild `gyb` from source locally with `pip`-installed deps, expect two
traps (both in `references/troubleshooting.md`): newer `httplib2` breaks the bundled
cacerts lookup, and copying the binary invalidates its code signature (→ `Killed: 9`).
For routine use, prefer the official prebuilt binary; the local patch matters only for
the `create-project` error UX, which you rarely re-run.
