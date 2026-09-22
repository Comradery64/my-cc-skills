Review the conversation so far, including any files created, modified, or referenced during the session. Then produce a SOC 2 compliance review:

## Session Summary
One-paragraph description of what was done in this session.

## Changes Made
Bullet each file created or modified, with a one-line description of the change.

## SOC 2 Relevant Actions
Categorize actions by Trust Service Criteria:
- **CC6 (Logical Access)** — any IAM, permissions, credentials, secrets, or access control changes
- **CC7 (System Operations)** — infrastructure changes, deployments, config changes
- **CC8 (Change Management)** — code or config changes, review/approval steps taken or skipped
- **A1 (Availability)** — changes affecting uptime, redundancy, or failover
- **C1 (Confidentiality)** — data handling, encryption, exposure of sensitive data
- **PI1 (Processing Integrity)** — logic changes that affect data correctness or completeness

Only include criteria where something relevant occurred. Omit empty categories.

## Risks & Gaps
Bullet any actions that may require follow-up for compliance:
- Missing approvals or review steps
- Secrets or credentials handled insecurely
- Overly broad permissions granted
- Changes made without audit trail
- Hardcoded values, unencrypted data, or public exposure risks

## Recommended Follow-ups
Bullet concrete next steps to close any gaps identified above.

Be specific — include file names, resource names, and exact issues. No filler.
