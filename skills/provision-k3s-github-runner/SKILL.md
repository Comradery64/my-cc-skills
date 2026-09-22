---
name: provision-k3s-github-runner
description: Provision a dedicated repo-level self-hosted GitHub Actions runner as a privileged docker-in-docker (DinD) pod in a k3s cluster, for a Docker build/push pipeline of a given GitHub repo. Use when a repo needs its own Linux x64 runner (real architecture, persistent workload) — e.g. an org/shared runner is inaccessible or a Mac/LaunchAgent runner is unsuitable. Ask for the target repo and reuse this exact procedure.
---

# Provision a k3s DinD self-hosted GitHub Actions runner

Creates a persistent, native-x86_64 self-hosted runner for one repo, using a
**one-time registration token + PersistentVolume** so **no standing admin
credential lives in the cluster**. Bundled files are in `assets/`.

## Inputs to gather first
- **REPO** (`owner/repo`) → `REPO_URL=https://github.com/owner/repo`
- **RUNNER_LABEL** — the `runs-on:` label. **Make it unique per project** (e.g.
  `linux-x64-k3s-docker-build-<proj>`) so it's unambiguous which backend built a run.
- **RUNNER_NAME** — e.g. `<proj>-k3s-runner` (also names the Deployment/PVC/Secret).
- **NAMESPACE** — default `ci-runners`.
- Confirm the user wants the DinD approach (privileged sidecar) and understands
  the tradeoff. **NEVER** substitute a host `/var/run/docker.sock` mount — it hands
  the pod root over the whole node; the DinD sidecar's `privileged:true` is scoped
  to its own nested daemon.

## Step 0 — Prerequisites (stop and confirm if any fail)
```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.architecture}'   # must be amd64/x86_64
kubectl get nodes --no-headers | wc -l                                     # single- vs multi-node
gh auth status                                                             # admin access to REPO
docker buildx version                                                      # a build tool (docker/nerdctl/podman)
```
- Arch **must** be `amd64` for a native (non-emulated) build. If not, stop and ask.
- Verify the runner can mint a registration token with existing `gh` auth (no PAT needed):
  ```bash
  gh api -X POST repos/<owner>/<repo>/actions/runners/registration-token \
    --jq 'if .token then "OK len=" + (.token|length|tostring) else "NO_TOKEN" end'
  ```
  If this fails, the account lacks admin on the repo — stop.

## Step 1 — Choose an image target
- **Multi-node cluster:** you MUST use a registry every node can pull from. Prefer an
  existing in-cluster registry — discover it:
  ```bash
  kubectl get svc -A | grep -Ei 'regist|harbor|zot'
  kubectl get deploy,sts -A -o jsonpath='{range .items[*]}{.spec.template.spec.containers[*].image}{"\n"}{end}' | sort -u | grep -i ':5000\|registry'
  ```
  Confirm reachability + that docker trusts it as insecure (if HTTP):
  ```bash
  curl -s -m5 -o /dev/null -w '%{http_code}\n' http://<REGISTRY>/v2/
  docker info --format '{{json .RegistryConfig.IndexConfigs}}' | tr ',' '\n' | grep <REGISTRY>
  ```
  `IMAGE=<REGISTRY>/<NAMESPACE>/<RUNNER_NAME>:latest`. Do NOT reuse the product's
  Docker Hub repo for this CI-infra image — keep them separate.
- **Single-node k3s:** no registry needed; import straight into containerd (Step 3 note).

## Step 2 — Namespace + build the runner image (native amd64)
```bash
kubectl create namespace <NAMESPACE> 2>/dev/null || true
# copy assets/ to a scratch dir, then:
docker build --platform linux/amd64 -t "$IMAGE" .    # entrypoint is idempotent (see assets/entrypoint.sh)
docker push "$IMAGE"                                  # multi-node
# single-node instead of push:  docker save "$IMAGE" | sudo k3s ctr images import -
```
Verify it is `linux/amd64` (query the registry manifest if imagetools rejects HTTP):
```bash
curl -s -H 'Accept: application/vnd.oci.image.index.v1+json' \
  http://<REGISTRY>/v2/<NAMESPACE>/<RUNNER_NAME>/manifests/latest | jq -c '.manifests[].platform'
```

## Step 3 — One-time registration token as a short-lived Secret
Mint via existing `gh` auth (no PAT stored). **Never echo the token**:
```bash
tok=$(gh api -X POST repos/<owner>/<repo>/actions/runners/registration-token --jq .token)
[ -n "$tok" ] && [ "$tok" != null ] && echo "minted len=${#tok}" || { echo FAIL; exit 1; }
kubectl create secret generic <RUNNER_NAME>-regtoken -n <NAMESPACE> --from-literal=token="$tok"
unset tok
```

## Step 4 — Render + apply the Deployment
Copy `assets/runner-deployment.yaml.tmpl`, replace every `__PLACEHOLDER__`
(`__NAMESPACE__ __RUNNER_NAME__ __RUNNER_LABEL__ __REPO_URL__ __IMAGE__
__STORAGE_CLASS__ __PVC_SIZE__`), then:
```bash
kubectl apply -f runner-deployment.yaml
kubectl -n <NAMESPACE> get pods -w        # wait for 2/2 Running (dind + runner)
```
- Pick a **replicated** storage class (e.g. `longhorn`) so state survives reschedule.
- If a container isn't Ready: `kubectl -n <NAMESPACE> logs deploy/<RUNNER_NAME> -c runner` / `-c dind`.
- DinD is healthy once its log shows `API listen on [::]:2375`.

## Step 5 — Verify, then delete the one-time Secret
```bash
kubectl -n <NAMESPACE> exec deploy/<RUNNER_NAME> -c runner -- bash -c 'docker version --format "server={{.Server.Version}} arch={{.Server.Arch}}"'
gh api repos/<owner>/<repo>/actions/runners --jq '.runners[] | {name,status,os,labels:[.labels[].name]}'
# expect the runner: status "online", os "Linux", with RUNNER_LABEL
kubectl -n <NAMESPACE> exec deploy/<RUNNER_NAME> -c runner -- ls /home/runner/.runner /home/runner/.credentials
kubectl -n <NAMESPACE> delete secret <RUNNER_NAME>-regtoken   # creds now persisted on PVC
```

## Step 6 — Point a workflow at it (separate reviewed PR)
Change the job's `runs-on:` to `<RUNNER_LABEL>`. Open a normal PR; do not merge
without the user asking.

## Known gotchas (baked into the assets, but watch for them)
- **Scoped Docker Hub token blocks public base pulls.** If the workflow logs into
  Docker Hub with a token scoped to only the product repo, pulling public bases
  (e.g. `nvidia/cuda`) 401s with "insufficient scopes". Fix in the *workflow*:
  `docker logout` before build so bases pull anonymously, then login only to push.
- **Do NOT isolate the build with an empty `DOCKER_CONFIG`** — it disables buildx and
  falls back to the legacy builder, which rejects `RUN --mount`. Use
  `DOCKER_BUILDKIT=1 docker build` and rely on `docker logout` for the anonymous pull.
- **Credentials persist on the PVC.** The login step writes `~/.docker/config.json`
  onto the runner's volume; it survives runs. `docker logout` at build start handles it.
- **macOS runners** only run while a user session is active (LaunchAgent) — this k3s
  pod avoids that. **buildx `--push` with the docker-container driver** needs the
  daemon; here the plain daemon (DinD) handles build+push fine.
- Verify Docker daemon health with a real API call (`docker ps`), not just `docker version`.

## Guardrails
- Never mount the host node's `/var/run/docker.sock` — always the DinD sidecar.
- `privileged:true` on the `dind` container only; `runner` stays unprivileged.
- Never store an admin-scoped PAT in the cluster; use the one-time-token + PVC path.
  (If the org blocks fine-grained PATs entirely, this path is also the fallback.)
- Never echo any token; create Secrets from a shell var / stdin, then `unset`.
- Keep the CI-infra runner image out of the product's Docker Hub repo.
- Give each project's runner a UNIQUE label.
