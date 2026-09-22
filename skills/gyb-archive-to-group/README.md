# gyb-archive-to-group

Offboard a Google Workspace user (or free up a shared mailbox address) without losing the mail and without paying for a dormant seat.

Backs up the mailbox with [GYB (Got Your Back)](https://github.com/GAM-team/got-your-back), renames the account to free its address, creates a Google Group at that address with conversation history on, restores the mail into the group's archive, then suspends the old account.

**Quick start:**
```sh
gyb --action estimate --email <target> --service-account
gyb --action backup --email <target> --service-account
scripts/verify_backup.sh "GYB-GMail-Backup-<target>"
```

Then rename the account and create the destination group in the admin console (manual, by design — see [SKILL.md](SKILL.md)), and restore:
```sh
gyb --action restore-group --email <group-address> --use-admin admin@example.com \
  --local-folder "GYB-GMail-Backup-<renamed-target>" --service-account
```

See [SKILL.md](SKILL.md) for the full workflow, argument semantics, and the sequencing gotchas (why rename has to happen between backup and group creation). See `references/project-setup.md` for one-time GCP/service-account setup and `references/troubleshooting.md` for known errors.

**Requirements:** GYB binary + a domain-wide-delegated service account, `sqlite3`, a Workspace super admin for the manual console steps.
