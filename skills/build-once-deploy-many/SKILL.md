---
name: build-once-deploy-many
description: Guide teams in adopting a "build once, deploy many" CI/CD pattern — replacing per-environment artifact rebuilds with immutable, promotable artifacts. Use this skill whenever the user mentions CI/CD pipelines, deployment strategies, artifact promotion, environment-specific builds, slow deployments, painful rollbacks, semver workflows, deploy automation, release engineering, or platform engineering improvements. Also trigger when someone describes symptoms like "we rebuild for each environment", "rollbacks take forever", "deploys are slow", "config is baked into the build", or asks how to speed up deployments and rollbacks. Even if the user doesn't use these exact words, trigger whenever the conversation involves making deploys faster, more reliable, or more repeatable across environments.
---

# Build Once, Deploy Many

This skill helps migrate teams from per-environment rebuild workflows to an immutable artifact promotion model. The core principle: build an artifact once, then promote that exact artifact through environments.

## The Anti-Pattern to Recognize

Teams following a semver-centric, rebuild-per-environment workflow typically look like this:

1. **Dev** — Build from a feature branch to get onto a dev environment.
2. **Staging** — Manually trigger a job to increment a shared semver tied to a main SHA, then rebuild the artifact.
3. **Production** — Rebuild the artifact again.
4. **Config** — Orchestration config is coupled with app code, not saved or versioned anywhere. Every change wipes the environment's history.
5. **Rollbacks** — Entirely manual because there's no prior artifact to fall back to.

Typical metrics for this pattern: deploys take 15–20 minutes, rollbacks take 30–45 minutes.

### Symptoms

Look for these when assessing a team's pipeline:

- The artifact is rebuilt for each environment (dev, staging, prod are separate builds).
- Environment-specific values (URLs, secrets, feature flags) are baked in at compile/bundle time.
- Rollbacks require rebuilding a previous version from scratch.
- No audit trail of which artifact is running where.
- Semver is incremented manually or mid-pipeline rather than at release time.
- A config change requires a full app redeploy.

---

## The Migration: Five Steps

### Step 1 — Externalize Environment-Specific Configuration

Work with application teams to pull environment-specific values out of static build artifacts and make them injectable at runtime. After this step, the built artifact should contain zero references to any specific environment.

**What to externalize:**
- API endpoints and service URLs
- Feature flags
- Database connection strings
- Secrets and credentials (use a secrets manager)
- Log levels and observability settings
- CDN and asset paths

**Runtime injection approaches by app type:**

- **Backend services**: Environment variables, config files mounted at deploy time, or a config server.
- **Frontend / static assets**: A runtime config file (e.g. `/config.json` fetched at app startup), server-side template replacement at serve time, or window-level globals injected by the serving layer.
- **Containers**: Environment variables, mounted ConfigMaps/Secrets (Kubernetes), or entrypoint scripts that substitute placeholders.

The litmus test: can you deploy the same artifact to dev and prod with only config differences? If yes, this step is done.

### Step 2 — Build Immutable Artifacts on Every Merge to Main

Every merge to main triggers a CI build that produces a single, immutable artifact — a container image, binary, bundle, or whatever the team ships.

- Tag the artifact with the commit SHA (and optionally a build number). Do not assign a semver here.
- Push the artifact to a registry (container registry, artifact repo, S3, etc.).
- The artifact is a snapshot of the code at that exact commit. It never changes.

### Step 3 — Version Configuration Separately

Configuration becomes its own versioned artifact, stored and tracked independently from application code.

Options include a separate repo, a dedicated directory, Helm values files, Kustomize overlays, Terraform variables, or a parameter store like AWS SSM.

Each environment has its own config version with full change history. This means:
- Config changes don't require an app rebuild.
- You can see exactly what config was active at any point in time.
- Config can be rolled back independently of application code.

### Step 4 — Promote Artifacts Through Environments

Instead of rebuilding, teams select a previously built artifact and deploy it to the next environment. The promotion flow:

1. Artifact is built once from main (Step 2).
2. Deploy to dev — run tests.
3. Promote the **same artifact** to staging — run tests.
4. Promote the **same artifact** to production.

At each stage, only the environment-specific config injected at deploy time changes. The artifact itself is identical.

Rollback becomes trivial: promote the previously known-good artifact again. Since it already exists in the registry, this is near-instant.

### Step 5 — Automate Semver and Release at Production Time

Defer semver assignment to the moment of production release:

1. A team member triggers the release (one button, or a merge to a release branch).
2. Automation calculates the next semantic version (via conventional commits, a version file, or manual input).
3. A release is cut with an auto-generated changelog.
4. The existing artifact is tagged with the semver for easy future lookup.

This keeps semver meaningful — it maps 1:1 to production releases — and decouples versioning from the build pipeline.

---

## Expected Outcomes

| Metric | Before | After |
|---|---|---|
| Deploy time | 15–20 min | ~15 seconds |
| Rollback time | 30–45 min | ~5 seconds |
| Artifact consistency | Different per env | Identical across envs |
| Config traceability | None | Full version history |
| Release tagging | Manual, mid-pipeline | Automated at release |

---

## Implementation Checklist

Use this when helping a team plan or execute the migration:

- [ ] Audit all environment-specific values currently baked into builds
- [ ] Implement runtime config injection for each application type
- [ ] Set up an artifact registry if one doesn't exist
- [ ] Configure CI to build once on merge to main and push to registry
- [ ] Create a separate config versioning strategy
- [ ] Build a promotion pipeline (dev → staging → prod) that deploys existing artifacts
- [ ] Implement one-button release automation (semver calculation, changelog, artifact tagging)
- [ ] Test rollback by promoting a previous artifact
- [ ] Document the new workflow for all teams
- [ ] Remove old per-environment rebuild jobs

---

## Common Objections

**"We need different build flags per environment."**
That's almost always configuration, not code. Move it to runtime injection. If something truly must differ at compile time, question whether it belongs in the app or in the platform layer.

**"Our frontend bakes in the API URL at build time."**
Serve a runtime config file (e.g. `/config.json`) that the app fetches on startup, or inject it via the web server's HTML templating. Most frameworks support this natively or with minimal wiring.

**"What about database migrations?"**
Migrations are a separate concern. Run them as a pre-deploy step, not as part of the artifact build. Version them alongside config or in their own pipeline.

**"We can't use containers."**
The pattern works with any artifact type — JARs, zips, tarballs, static bundles. The key principle is immutability and environment-agnosticism, not containerization.

---

## Concrete Implementation: Next.js + ECS Fargate + AWS (a real-world example)

This section documents the exact implementation built for a production testing-platform service. Use it as a reference when deploying the same stack.

### Infrastructure Overview

```
Shared Services account
└── ECR repo: testing-platform (single shared repo, IMMUTABLE tags, KMS-encrypted)
    └── stacks/shared/testing-platform-ecr/ (own Terraform stack, prevent_destroy = true)

Per-environment (dev/staging/prod account)
└── ECS Fargate cluster: testing-platform-<env>
└── IAM role: testing-platform-<env>-app-deploy  ← assumed by GitHub Actions via OIDC
└── Secrets Manager: testing-platform/<env>/<secret-name>  ← runtime secrets, no values in TF
```

### 1. Shared ECR (one-time setup)

- Single repo in Shared Services, NOT per-environment
- Tags: `IMMUTABLE` — forces new push for every change, prevents overwrites
- Lifecycle policy: keep 50 images (prune oldest)
- Image tag format: `sha-<full-git-sha>` — immutable, traceable to commit

### 2. Per-Environment Deploy Role

OIDC trust scoped to the GitHub Environment (not just the repo):
```
repo:your-org/your-frontend-repo:environment:<env>-testing-platform
```

ECRPush policy must include **both** the exact repo ARN and the wildcard — the wildcard alone (`testing-platform-*`) will NOT match `testing-platform`:
```hcl
Resource = [
  "arn:aws:ecr:us-west-1:${account_id}:repository/testing-platform",
  "arn:aws:ecr:us-west-1:${account_id}:repository/testing-platform-*"
]
```

ECS permissions needed: `ecs:DescribeServices`, `ecs:UpdateService`, `ecs:DescribeTaskDefinition`, `ecs:RegisterTaskDefinition`, `ecs:ListTaskDefinitions`, `iam:PassRole` (scoped to task roles).

### 3. GitHub Environments

One environment per deploy target: `dev-testing-platform`, `staging-testing-platform`, `prod-testing-platform`.

| Type | Key | Value |
|------|-----|-------|
| Secret | `AWS_DEPLOY_ROLE_ARN` | IAM role ARN from `terraform output frontend_deploy_role_arn` |
| Variable | `NEXT_PUBLIC_APP_URL` | e.g. `https://dev.platform.example.com` |
| Variable | `NEXT_PUBLIC_APP_ENV` | `development` / `staging` / `production` |
| Variable | `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | public Turnstile key |
| Variable | `NEXT_PUBLIC_GITHUB_MODELS_COMMIT` | commit SHA |

`NEXT_PUBLIC_*` values must be **variables** (not secrets) — they are passed as `--build-arg` and end up in the public bundle. Runtime secrets live in AWS Secrets Manager, not GitHub.

### 4. Dockerfile (Next.js standalone)

Multi-stage build: `base → deps → builder → runner`

Critical requirements:
- Enable `output: 'standalone'` in `next.config.js` — produces minimal self-contained server
- Copy `prisma/` before `pnpm install` — postinstall runs `prisma generate` and needs the schema
- Runner stage copies: `.next/standalone/`, `.next/static/`, `public/`
- Run as non-root (`nextjs:nodejs` user, uid/gid 1001)
- `HEALTHCHECK` via wget against `/api/health`

```dockerfile
FROM base AS deps
COPY package.json pnpm-lock.yaml ./
COPY prisma ./prisma          # ← required before pnpm install
RUN pnpm install --frozen-lockfile
```

### 5. CI/CD Workflow (deploy.yml)

```yaml
on:
  push:
    branches: [dev]   # add staging/main only after those stacks are applied

jobs:
  deploy:
    environment: ${{ ... }}-testing-platform   # loads env-scoped secrets + vars
    steps:
      - Configure AWS credentials (OIDC)
      - Login to Amazon ECR
      - docker build --build-arg NEXT_PUBLIC_*=... -t sha-${{ github.sha }}
      - docker push
      - describe-task-definition → patch image → register-task-definition → update-service
```

ECS deploy sequence (no ECS deploy action needed — plain AWS CLI):
1. `aws ecs describe-task-definition` — get current task def, strip read-only fields with `jq del(...)`
2. Patch `.containerDefinitions[0].image` with new SHA-tagged image
3. `aws ecs register-task-definition` — get new ARN
4. `aws ecs update-service --force-new-deployment` — rolls out new tasks

### 6. Runtime Secrets via Secrets Manager

Terraform creates the secret shells (no values). Values are written separately from 1Password:

```bash
# Secure: pipe directly, never touch stdout
op item get "<item-id>" --format json \
  | jq -r '.fields[] | select(.label == "notesPlain") | .value' \
  | grep -E '^KEY=".+"' \
  | while IFS='=' read -r key rest; do
      val="${rest#\"}"; val="${val%\"}"
      aws secretsmanager put-secret-value \
        --secret-id "app-name/env/$(echo "$key" | tr '[:upper:]' '[:lower:]' | tr '_' '-')" \
        --secret-string "$val" --output text --query VersionId
    done
```

ECS execution role needs `secretsmanager:GetSecretValue` + `kms:Decrypt` on all secret ARNs. Secrets are injected via the task definition `secrets` block (not `environment`).

### Key Lessons

**IAM wildcard pitfall** — `repository/testing-platform-*` does NOT match `repository/testing-platform`. Always include the exact ARN alongside any wildcard when the base name is also a valid resource.

**Next.js build-time env vars** — `NEXT_PUBLIC_*` values are baked into the bundle at build time. They cannot be injected at runtime. Pass them as GitHub Environment *variables* (not secrets) via `--build-arg`. This means a true single-image promotion across environments is not possible for Next.js apps — each environment gets a separate build with its own public vars baked in.

**Lazy-init SDK clients** — Never instantiate SDK clients (Resend, Stripe, OpenAI, etc.) at module level in Next.js. Static page collection during `next build` evaluates all route modules, and any constructor that throws when an env var is absent will crash the build. Always initialize inside the handler function:
```typescript
// ✗ crashes at build time
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!)

// ✓ safe
export async function POST(req) {
  const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!)
  ...
}
```

**ACM certificate CAA records** — Before requesting an ACM certificate, verify the domain's CAA records permit Amazon's CA. Must include `0 issue "amazon.com"` and `0 issue "amazontrust.com"`. Missing CAA entries cause `CAA_ERROR` and the certificate will never validate.

**Long-lived branches** — Never use `--delete-branch` on `gh pr merge` for `dev`, `staging`, or `main`. These are permanent branches, not feature branches. The flag is only appropriate for short-lived feature branches.

**Workflow trigger scope** — Only add a branch to the `deploy.yml` trigger (`branches: [dev, staging, main]`) once that environment's Terraform stack has been applied and `AWS_DEPLOY_ROLE_ARN` is set in the corresponding GitHub Environment. Triggering before setup causes OIDC failures on every push to that branch.
