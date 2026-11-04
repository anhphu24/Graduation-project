#!/usr/bin/env bash
set -euo pipefail

# Runs only on a GitHub Actions runner. The reviewed deploy_ec2.sh is streamed
# over SSH; no secret, database or application file is uploaded by this script.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_HOST="${DEPLOY_HOST:-}"
DEPLOY_SSH_PORT="${DEPLOY_SSH_PORT:-22}"
DEPLOY_USER="${DEPLOY_USER:-ubuntu}"
TARGET_SHA="${TARGET_SHA:-}"
MAIN_SHA="${MAIN_SHA:-}"
DEPLOY_MODE="${DEPLOY_MODE:-}"
SSH_PRIVATE_KEY="${SSH_PRIVATE_KEY:-}"
SSH_KNOWN_HOSTS="${SSH_KNOWN_HOSTS:-}"

fail() { echo "SSH deployment preflight failed: $*" >&2; exit 2; }
[[ "${DEPLOY_HOST}" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] || fail "DEPLOY_HOST must be a DNS name or IPv4 address."
[[ "${DEPLOY_SSH_PORT}" =~ ^[0-9]{1,5}$ ]] || fail "DEPLOY_SSH_PORT must be numeric."
(( 10#${DEPLOY_SSH_PORT} >= 1 && 10#${DEPLOY_SSH_PORT} <= 65535 )) || fail "Invalid SSH port."
[[ "${DEPLOY_USER}" == "ubuntu" ]] || fail "Only the preconfigured ubuntu deployment user is allowed."
[[ "${TARGET_SHA}" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid TARGET_SHA."
[[ "${MAIN_SHA}" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid MAIN_SHA."
[[ "${DEPLOY_MODE}" == deploy || "${DEPLOY_MODE}" == rollback ]] || fail "Invalid DEPLOY_MODE."
[[ -n "${SSH_PRIVATE_KEY}" ]] || fail "SSH_PRIVATE_KEY secret is missing."
[[ -n "${SSH_KNOWN_HOSTS}" ]] || fail "SSH_KNOWN_HOSTS secret is missing."
[[ -f "${PROJECT_ROOT}/scripts/deploy_ec2.sh" ]] || fail "Reviewed deployment script is missing."

secret_dir="$(mktemp -d "${RUNNER_TEMP:-/tmp}/food-rescue-ssh.XXXXXXXX")"
trap 'rm -rf -- "$secret_dir"' EXIT
chmod 700 "$secret_dir"
umask 077
printf '%s\n' "$SSH_PRIVATE_KEY" > "$secret_dir/id_ed25519"
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$secret_dir/known_hosts"
chmod 600 "$secret_dir/id_ed25519" "$secret_dir/known_hosts"

ssh-keygen -y -P '' -f "$secret_dir/id_ed25519" >/dev/null || fail "Invalid or encrypted SSH private key."
known_host="$DEPLOY_HOST"
if [[ "$DEPLOY_SSH_PORT" != "22" ]]; then
    known_host="[$DEPLOY_HOST]:$DEPLOY_SSH_PORT"
fi
ssh-keygen -F "$known_host" -f "$secret_dir/known_hosts" >/dev/null || fail "Verified SSH host key is missing."

remote_ssh() {
    ssh -T -o BatchMode=yes -o IdentitiesOnly=yes \
        -o StrictHostKeyChecking=yes \
        -o UserKnownHostsFile="$secret_dir/known_hosts" \
        -o GlobalKnownHostsFile=/dev/null \
        -o ConnectTimeout=15 \
        -o ForwardAgent=no -o ClearAllForwardings=yes \
        -i "$secret_dir/id_ed25519" \
        -p "$DEPLOY_SSH_PORT" \
        "${DEPLOY_USER}@${DEPLOY_HOST}" "$@"
}

echo "Checking SSH connectivity and non-interactive sudo..."
remote_ssh 'sudo -n true' </dev/null
echo "Deploying reviewed code to Food Rescue EC2 over SSH..."
remote_ssh "sudo -n env EXPECTED_SHA=$TARGET_SHA EXPECTED_MAIN_SHA=$MAIN_SHA DEPLOY_MODE=$DEPLOY_MODE APP_DIR=/var/www/food-rescue APP_USER=ubuntu /bin/bash -s" \
    < "$PROJECT_ROOT/scripts/deploy_ec2.sh"
