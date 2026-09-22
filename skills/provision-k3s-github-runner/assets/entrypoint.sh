#!/usr/bin/env bash
set -euo pipefail

: "${REPO_URL:?REPO_URL is required}"
: "${RUNNER_LABELS:?RUNNER_LABELS is required}"
RUNNER_NAME="${RUNNER_NAME:-k3s-runner-$(hostname)}"

# Idempotent registration. The runner directory lives on a persistent volume, so
# once config.sh has written .runner + .credentials the runner re-authenticates
# to GitHub on its own across restarts — no registration token is needed again.
# A registration token (REG_TOKEN) is required ONLY for the very first boot and is
# injected from a short-lived, one-time Secret that is deleted after registration.
if [ ! -f "$HOME/.runner" ]; then
  : "${REG_TOKEN:?First-time registration needs REG_TOKEN (mint via: gh api -X POST repos/<owner>/<repo>/actions/runners/registration-token)}"
  echo "No existing runner config found — registering..."
  ./config.sh --url "$REPO_URL" \
    --token "$REG_TOKEN" \
    --name "$RUNNER_NAME" \
    --labels "$RUNNER_LABELS" \
    --unattended \
    --replace
else
  echo "Existing runner config found on persistent volume — skipping registration."
fi

# No admin-scoped credential is stored in the cluster, so we cannot mint a removal
# token to auto-deregister on shutdown. Leave the runner registered; it just shows
# offline until it restarts (or is removed manually with a fresh removal token).
cleanup() {
  echo "Stop signal received — leaving runner registered (no admin token to auto-deregister)."
}
trap cleanup TERM INT

./run.sh & wait $!
