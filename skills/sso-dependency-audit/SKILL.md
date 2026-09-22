---
name: sso-dependency-audit
description: Audits which third-party services are tied to a Google Workspace account's identity via SAML SSO or "Sign in with Google" OAuth, and checks whether each has a non-Google fallback login — before changing how that account authenticates (converting a shared mailbox to a Google Group, deprovisioning, enforcing a new IdP, killing a shared password, etc.). Read-only: gathers evidence via GAM, never mutates the account. Use whenever someone asks things like "can we convert X to a Google Group", "what will break if we change how X logs in", "audit SSO for X", "check SAML/SSO logins for X", "what services use Sign in with Google for X", or "is it safe to kill the password on this account" — trigger even if they don't say "SSO" or "SAML" explicitly, since the underlying question is always the same: what depends on this Google identity being able to log in.
---

# SSO / Federated-Login Dependency Audit (GAM7)

## What this answers

Before an account's ability to authenticate *as itself* goes away — converted to a Google Group,
suspended, or moved behind a different IdP — find every third-party service that currently trusts
*this Google identity* to log in, and determine whether each one can fall back to a non-Google login
(typically email + password) so the dependency can be broken cleanly instead of silently.

This is investigative only. It never suspends, converts, revokes tokens, or resets anything — it
produces a report for a human to act on. If asked to also perform the migration, treat that as a
separate follow-up step, not part of this audit.

## Setup

Locate GAM before anything else — don't assume a path, since it varies by machine:

```bash
GAM=$(command -v gam || echo ~/bin/gam7/gam)
"$GAM" version   # confirms auth + shows the authorized domain/customer ID
```

If `gam version` fails or shows the wrong domain, stop and ask rather than guessing at an
unauthenticated or wrong-tenant binary.

## Step 1 — True SAML SSO logins (Google as IdP)

```bash
"$GAM" report saml user <email> previousmonths 6
```

`previousmonths` caps at 6 — GAM rejects anything higher (`Expected <integer 1<=x<=6>`), and that's
also the practical retention ceiling for this report, so 6 gets you the most complete window
available. Omitting the date argument entirely also defaults to full retention, if you want a
second read.

Read `name` (`login_success`/`login_failure`), `application_name` (the SAML SP's display name —
blank on failures like `failure_app_not_enabled_for_user`, since the app was never actually
reached), and `initiated_by` (`sp` = the user started at the vendor; `idp` = they started from the
Google app launcher).

**Zero rows is a real, meaningful finding, not an error to explain away.** It means this identity
has never completed a SAML SSO login via Google in the retention window. Say so plainly in the
report rather than treating it as "nothing to look at here."

## Step 2 — OAuth "Sign in with Google" grants (usually the bigger source of dependencies)

Shared mailboxes and service accounts more often authenticate to vendor tools through consumer-style
"Sign in with Google" (OIDC) rather than enterprise SAML. Don't skip this step regardless of what
Step 1 found — it's frequently where the real dependencies live.

```bash
"$GAM" user <email> show tokens
```

For each grant, `displayText` is the vendor's app name and `scopes` tells you what kind of grant it
is:

- Scopes limited to `userinfo.email` + `userinfo.profile` + `openid` → pure federated login. This
  account's ability to *sign in* to that vendor depends on this Google identity — exactly what this
  audit exists to find.
- Broader scopes (Drive, Calendar, Gmail, etc.) → a data-access integration, not a login dependency.
  It won't stop anyone from logging into that vendor's product with a different credential, so keep
  it out of the login-*replaceability* table — but don't let it fade into soft prose either. Name the
  actual scope and translate it plainly: `https://mail.google.com/` is full read/write/send/delete
  access to the entire mailbox, not "the app can sync mail." Underselling a full-mailbox or
  full-drive grant as a minor convenience is a worse miss than not mentioning it at all — list every
  data-access grant explicitly (see Step 5) rather than folding it into a paragraph.

Filter out Google's own first-party clients before counting anything as a third-party finding — e.g.
client ID `77185425430.apps.googleusercontent.com` is Google Chrome's own sign-in, not an
integration. Any client ID that resolves to a Google-owned app is noise here.

## Step 3 — Account context

```bash
"$GAM" info user <email>
```

Pull Org Unit Path, Groups, 2-Step Verification enrolled/enforced status, Recovery Email/Phone, and
anything listed under "Other Emails." That last one matters more than it looks — a secondary "work"
email often belongs to an external party (a contractor, an outsourced bookkeeper, an agency) who
actually uses this shared login day to day and needs to be told about the change *before* it
happens, not discover it after.

Group memberships deserve a second look too: a group can feed a downstream SSO/SCIM integration
(e.g. an AWS Identity Center or 1Password sync) even when this specific account has never personally
completed a SAML login through it. That's a different risk surface than "this account authenticated
to X" — keep the two distinct in the writeup instead of conflating them.

## Step 4 — Per-service fallback research

For every distinct service surfaced in Step 1 or Step 2, research whether it supports a non-Google
login (email/password, magic link, etc.) as an alternative to the Google-linked sign-in — most
consumer-style "Continue with Google" integrations do, typically via a password-reset flow that
detaches the Google link in the process.

Always attach this caveat rather than presenting a clean yes/no: whether that fallback is actually
*available on this specific account* depends on settings inside that vendor's own admin console
(e.g., an org-enforced SSO policy configured on the vendor's side). Google's audit logs can only
prove *that* this account used Google to log in — never whether the vendor requires it exclusively.

Put a short version of this directly in each row's *Caveats* cell — even five words like "vendor may
enforce SSO — verify" satisfies it. This is a floor, not a menu: a row often also deserves its own
distinct caveat (e.g. "this account may never have set a password here," or "this grant's scope is
ambiguous about whether it also covers login") — add that too, but it goes *alongside* the
SSO-enforcement line, never in place of it. A row that raises a different, genuinely useful concern
instead of this one is still missing the one thing every row needs, because the two questions are
independent: whether *this account* happens to have a password is a different question from whether
*the vendor* would let it use one even if it did. On audits with many services, the temptation is to
state the caveat once in prose below the table and let it cover everything; that's the exact pattern
to avoid, since a reader skimming just the table loses the warning entirely. If a service genuinely
needs a longer explanation, put the short version in the cell and the detail in a footnote below it
— the footnote supplements the cell, it doesn't substitute for it.

## Step 5 — Report

Structure the findings this way every time, so the output is scannable regardless of how many
services turned up:

```
## Findings
[One line: total SAML logins found + retention window, e.g. "Zero SAML SSO logins in the full
6-month retention window."]

| Service | Auth type found | Replaceable with non-Google login? | Caveats |
|---|---|---|---|
...

## Bottom line
[Clear verdict — clear to proceed / blocked by X — plus the specific pre-migration action for each
service that needs one, e.g. "reset the password in Deel before converting the account, to detach
the Google link."]
```

If Step 2 also turned up data-access-scoped grants (Drive, Calendar, Gmail, etc.), give them their
own short table right after the login-risk one — don't bury them in a paragraph, since that's how a
full-mailbox grant ends up softened into "potentially syncs some mail":

```
## Data-access grants (not login dependencies, but break silently on conversion)
| Service | Scope | What it actually allows |
|---|---|---|
...
```

These don't get a replaceability verdict — a Group can't be "replaced" out of a data grant the way a
login can — but they need an owner conversation before conversion, and the report should say so.

Anything from Step 3 that isn't itself a login dependency but still matters for the migration (an
external party who relies on the account, a group that feeds a downstream integration) belongs in a
short side-note below the tables — it's a different kind of risk than "will this login break," so
don't fold it into either table's rows.

## Gotchas

- `gam print inboundssoprofile` / `inboundssocredential` / `inboundssoassignment` check a *different*
  thing entirely — whether an external IdP is trusted to log **into** Google. It says nothing about
  whether Google acted as SAML IdP **for** this account logging into third-party apps, which is what
  Step 1 answers. Don't substitute one for the other, even though both frequently come back empty on
  the same tenant — they're unrelated settings, and reporting "no inbound SSO configured" as if it
  answered the Step 1 question is a real, observed mistake, not a hypothetical one.
- `gam report saml` and `gam report login` are different report types with different columns — don't
  reuse column names between them. `report saml` failures carry a `failure_type` (e.g.
  `failure_app_not_enabled_for_user`) instead of an `application_name`.
- `show tokens` only lists *currently live* grants. A revoked token isn't a forward-looking risk for
  this audit, so there's no need to chase down history for it — the point is protecting what's still
  active.
- This audit only covers Google-mediated logins. A service the account reaches with its own
  independent, unrelated username/password won't show up here at all — that's expected coverage, not
  a gap.
