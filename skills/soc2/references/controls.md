# SOC 2 Trust Service Criteria — what to look for in code, infra, and PRs

Evidence-driven. Each bullet is a thing you can find or confirm absent in the target. "Type 2" column: how to confirm the control operates over time, not just exists.

## CC6 — Logical and Physical Access
- Secrets: none in code, env files, CI YAML, Dockerfiles, tfvars, commit history (`git log -p -S` for key prefixes). Managed via Vault/1Password/GitHub Secrets/cloud secret manager.
- IAM/RBAC: least privilege, resource-scoped actions, no `Action: *` with `Resource: *`, no long-lived static cloud keys in CI (OIDC instead).
- Authentication: MFA enforced where configurable, session timeout/rotation, password/token policy, no shared accounts, service accounts named and scoped.
- Network: no `0.0.0.0/0` ingress on non-public ports, private subnets for data stores, security groups scoped, TLS termination.
- Access lifecycle: joiner/mover/leaver handled (Terraform-managed users, SCIM, offboarding scripts). Removal of access is committed, not manual.
- Type 2: access changes go through PR with reviewer; periodic access review artefacts exist (script, scheduled job, doc with dates).

## CC7 — System Operations
- Logging: auth events, admin actions, data access logged; logs shipped centrally; retention set; logs cannot be deleted by the service writing them.
- Monitoring/alerting: health checks, error-rate and security alerts defined as code; on-call routing.
- Vulnerability management: dependency scanning (Dependabot/Renovate/Snyk/trivy), image scanning, IaC scanning (checkov/tfsec) in CI and blocking.
- Incident response: runbook or IR doc referenced; alerts route somewhere owned.
- Type 2: scans run on every PR and on schedule; alert configs versioned; evidence of remediation (merged Dependabot PRs, closed findings).

## CC8 — Change Management
- Branch protection: PR required, ≥1 approving review from non-author, CI status checks required, no force-push, admins included.
- CI: tests + lint + security scan gate merges; workflows pinned by full SHA; no `pull_request_target` with checkout of untrusted code; minimal `permissions:` block.
- Deployment: separate envs, promotion path, rollback documented, IaC plan reviewed before apply, no console/manual changes (drift detection).
- Emergency changes: break-glass path defined and logged.
- Type 2: sample recent merges — all via PR, all reviewed, all CI green. Direct pushes to main = finding.

## CC9 — Risk Mitigation and Vendors
- Third-party services and SDKs identified; vendor list or SBOM exists; licenses reviewed.
- Data shared with vendors documented (what, why, DPA).

## A1 — Availability
- Backups: automated, encrypted, tested restore, retention defined, cross-region where warranted.
- Redundancy: multi-AZ for data stores, autoscaling or capacity plan, health-checked load balancing.
- DR/BCP: RTO/RPO stated; restore test evidence dated.
- Type 2: backup jobs succeed on schedule; restore drills recorded.

## C1 — Confidentiality
- Encryption at rest (KMS/CMK, EBS/RDS/S3 encryption) and in transit (TLS ≥1.2, HSTS, no plaintext internal hops for sensitive data).
- Data classification: PII/PHI/payment data identified; not in logs, error messages, test fixtures, analytics.
- Storage exposure: no public buckets, no public snapshots, signed URLs with expiry.
- Data deletion/retention implemented, not just documented.

## PI1 — Processing Integrity
- Input validation at trust boundaries; schema enforcement; idempotency on mutating endpoints.
- Data pipelines: checksums, row counts, reconciliation, failure alerts, replay safety.
- Tests cover the correctness path for changed logic; migrations reversible.

## P — Privacy (only if PII is in scope)
- Consent/notice recorded; data minimisation; subject access and deletion supported; cross-border transfer noted.

## AI Inference and Tooling
Apply whenever the target serves models, handles prompts, ships kernels, or publishes OSS artifacts.

- Tenant isolation (CC6, C1): shared GPUs isolate tenants by process/container/MIG; KV cache and prefix cache scoped per tenant or cleared between them; batching cannot leak tokens across requests; tests cover cross-request isolation.
- Prompt and completion data (C1, P): inputs/outputs not logged at any level in prod, not in traces, metrics labels, or error reports; retention and deletion defined in code or config; opt-in only for training/eval reuse.
- Model and weight supply chain (CC7, CC8): weights verified by checksum or signature before load; `trust_remote_code` off by default; no `pickle`/`torch.load` on untrusted files without `weights_only`; model source and version pinned and recorded.
- OSS contribution governance (CC8): fork PRs run without secrets; no unsafe `pull_request_target`; maintainer review required; release workflow has a controlled publisher, signed artifacts (Sigstore/attestations), and pinned build deps.
- Inference API (CC6, A1): auth on every endpoint including health/metrics if exposed; per-tenant rate limits and quotas; request size and token limits; abuse and auth-failure logging.
- GPU availability (A1): model-server health checks, queue depth limits and backpressure, capacity failover across nodes/regions, graceful drain on deploy.
- Subprocessors (CC9): GPU clouds, model hosts, telemetry vendors listed with DPAs; telemetry is opt-in and documented.
- Native code (CC7, PI1): CUDA/C++ changes covered by sanitizer or fuzz runs in CI; kernel numerics tested against reference.

Recommended TSC scope for an inference vendor: Security + Availability + Confidentiality. PI1 only if output correctness is contracted. Privacy only if end-user PII is processed directly.

## GPU Platform / Control Plane
Apply to any control plane that hands developers GPU capacity, node access, or inference routing.

**CC6 — access and identity**
- Every new route is classified (public / user / admin) and wrapped in the auth middleware or decorator; count of decorated routes equals count of routes in admin routers.
- Auth cannot be off by default: `auth_enabled`, `DEV_MODE`, path whitelists, and bypass flags only reachable in local/dev targets, never in prod config or Helm defaults.
- Per-resource ownership check on anything that mints or returns credentials (SSH sessions, exec, tokens, kubeconfigs): scoped to the caller's own node/devbox/job, not to cluster or org membership.
- Tenant scoping in data access: queries on jobs/workloads/devboxes filter by owner id unless the caller is verified admin; no "list all" default.
- Node/agent identity: per-node credentials, not a shared install token; node id verified against the credential; machine tokens envelope-encrypted at rest with encryption context.
- SSH to nodes uses host-key verification (known-hosts/TOFU store), never `InsecureIgnoreHostKey`.
- Kubernetes RBAC for platform service accounts justified per verb; expansion of `secrets`, `pods/exec`, `roles`, `rolebindings` needs explicit review.
- Sessions revoked on org/team removal (periodic re-check); session identifiers not stored in cleartext.

**CC6/C1 — secrets and crypto**
- Field-level encryption for stored credentials (`_enc` columns or equivalent) always routed through the shared crypto helper; new secret-bearing fields never plaintext.
- Master key has a key id and a rotation path; single static AES key with no versioning is a finding.
- Secrets loaded from a secret manager at boot and fail closed if unreachable; no `.env` in prod; no secrets in Launch Template userdata, `/proc` cmdline (`echo pw | sudo -S`), or CI logs.

**CC6/C1 — workload and GPU isolation**
- Isolation runtime matches declared trust: untrusted or multi-tenant jobs get VM isolation (Firecracker), not the Docker default; PRs cannot silently downgrade.
- Per-developer OS users, sudoers, and `CUDA_VISIBLE_DEVICES` scoping on shared boxes; SSH key revocation path tested.
- Job `Env` maps and specs (which carry tenant secrets) never logged at INFO or above; prod log level not DEBUG.
- Inference request/response bodies transiting Redis or gateways are not persisted or logged; Redis write access treated as traffic-redirect capability.
- Node telemetry ships metadata only (path, kind, owner), never file contents.

**CC7 — operations**
- New failure modes wired to metrics and alerts (Prometheus/Grafana); fault-tolerance and sweeper toggles not disabled by default.
- Image scanning (Trivy) and Go vuln scanning (govulncheck) run on every image build; every ignore entry has CVE, owner, and reachability rationale.
- Admin SSH/exec sessions to nodes logged with identity and timestamp; audit action registry updated when new admin actions are added.

**CC8 — change and deploy**
- Deploy only from CI via OIDC role; laptop-to-prod deploy guard intact.
- Rolling/canary restart with health-gated waves and auto-abort for fleet changes; Launch Template / userdata drift check runs before rotation.
- Config added to userdata or env also flows through the template republish step — a missed step here can silently desync running nodes from the declared config for days before anyone notices.
- CI path-gating covers new modules; new images have a build workflow that includes the scan job.

**CC9 — vendors and hardware handoff**
- New external calls (managed inference/model hubs, remote-access tunnels, observability SaaS, GPU rental providers, chat/incident tooling, container registries) recorded with credential source and blast radius in the threat model doc.
- Vendor/reassigned GPU boxes follow wipe → harden → onboard → drift-check; no reordering or skipped wipe. Residual prior-tenant data is a C1 finding.
- Sanitization scripts soft-delete first with a defined recovery window; hard-delete flags need explicit invocation.

**A1 — availability**
- Multi-instance control plane keeps state in a shared datastore (RDS/DynamoDB/Redis), never in-memory only; PITR on state tables.
- Agent code recovers panics; health-check timeouts and ASG settings reviewed when changed.

**PI1 — billing and placement integrity**
- Credit/bid/usage ledgers mutate via transactions with idempotent replay; token/GPU-hour metering is reproducible from logs.
- GPU family matching is exact-token, allocator arithmetic is additive across sources, RuntimeClass not hardcoded.

**Evidence that counts**
- Dated internal audits and a risk-acceptance register (`docs/security/*.md`, ARCHITECTURE "known gaps") tracking OPEN vs FIXED.
- Pre-commit: `detect-private-key`, import boundary linting, heredoc injection guard.
- OIDC CI auth, SHA-pinned actions, Trivy + govulncheck gates, KMS-encrypted S3/RDS/EBS, DynamoDB PITR with encrypted audit export, CloudFront OAC.

## Quick red flags (any of these is at least High)
- `AKIA`, `sk-`, `ghp_`, `-----BEGIN`, `password=` in tracked files or history
- `Action: "*"` + `Resource: "*"`; `0.0.0.0/0` on 22/3306/5432/6379/27017
- `permissions: write-all` or missing `permissions:` in workflows with secrets
- `curl | sh` or unpinned `@main`/`@v3` actions in a deploy workflow
- `acl = "public-read"`, `publicly_accessible = true`, `storage_encrypted = false`
- Direct commits to `main`/`prod` without PR in the last 50 commits
- `auth_enabled.*False`, `DEV_MODE`, `_WHITELIST_PATHS` additions, `InsecureIgnoreHostKey`, `InsecureSkipVerify`, `curl -k`
- `select(Workload)` or similar without an owner filter; `_enc` field without `Encrypt`/`Decrypt` call; `echo .*| sudo -S`
- `verbs: ["*"]` or new `secrets`/`rolebindings` verbs in chart RBAC; `os.ReadFile` in telemetry code; `--hard-delete`/`--force` outside sanctioned scripts
- `trust_remote_code=True` default, `torch.load` without `weights_only=True`, prompts in `logger.info/debug` in prod paths
