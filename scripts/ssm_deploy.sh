#!/usr/bin/env bash
set -euo pipefail

INSTANCE_ID=""
APP_USER="ubuntu"
APP_DIR="/var/www/food-rescue"
EXPECTED_SHA=""
DEPLOY_MODE="deploy"

while (($#)); do
    case "$1" in
        --instance-id) INSTANCE_ID="${2:-}"; shift 2 ;;
        --app-user) APP_USER="${2:-}"; shift 2 ;;
        --app-dir) APP_DIR="${2:-}"; shift 2 ;;
        --expected-sha) EXPECTED_SHA="${2:-}"; shift 2 ;;
        --mode) DEPLOY_MODE="${2:-}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

[[ "$INSTANCE_ID" =~ ^i-[0-9a-f]+$ ]] || { echo "Invalid EC2 instance ID." >&2; exit 2; }
[[ "$APP_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "Invalid EC2 app user." >&2; exit 2; }
[[ "$APP_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || { echo "Invalid EC2 app directory." >&2; exit 2; }
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Expected SHA must contain 40 lowercase hex characters." >&2; exit 2; }
[[ "$DEPLOY_MODE" == "deploy" || "$DEPLOY_MODE" == "rollback" ]] || { echo "Mode must be deploy or rollback." >&2; exit 2; }

for command_name in aws python3; do
    command -v "$command_name" >/dev/null || {
        echo "Required command is unavailable: $command_name" >&2
        exit 3
    }
done

read -r -d '' remote_script <<EOF || true
set -euo pipefail
APP_DIR='$APP_DIR'
APP_USER='$APP_USER'
EXPECTED_SHA='$EXPECTED_SHA'
DEPLOY_MODE='$DEPLOY_MODE'

[[ "\$(id -u)" -eq 0 ]] || { echo 'SSM command must run as root.' >&2; exit 20; }
id "\$APP_USER" >/dev/null
test -d "\$APP_DIR/.git"
APP_HOME="\$(getent passwd "\$APP_USER" | cut -d: -f6)"

git_as_app() {
    runuser -u "\$APP_USER" -- env HOME="\$APP_HOME" git -C "\$APP_DIR" "\$@"
}

[[ -z "\$(git_as_app status --porcelain --untracked-files=all)" ]] || {
    echo 'EC2 working tree is not clean.' >&2
    exit 21
}

git_as_app fetch --no-tags origin main
origin_main="\$(git_as_app rev-parse refs/remotes/origin/main)"

if [[ "\$DEPLOY_MODE" == 'deploy' ]]; then
    [[ "\$EXPECTED_SHA" == "\$origin_main" ]] || {
        echo 'Expected SHA does not match origin/main.' >&2
        exit 22
    }
else
    git_as_app merge-base --is-ancestor "\$EXPECTED_SHA" "\$origin_main" || {
        echo 'Rollback target is not in origin/main history.' >&2
        exit 23
    }
fi

deployment_script="\$(mktemp /tmp/food-rescue-deploy.XXXXXX)"
trap 'rm -f "\$deployment_script"' EXIT
git_as_app show "\${origin_main}:scripts/deploy_ec2.sh" > "\$deployment_script"
chmod 0700 "\$deployment_script"

EXPECTED_SHA="\$EXPECTED_SHA" \
DEPLOY_MODE="\$DEPLOY_MODE" \
APP_DIR="\$APP_DIR" \
APP_USER="\$APP_USER" \
bash "\$deployment_script"
EOF

parameters_file="$(mktemp)"
trap 'rm -f "$parameters_file"' EXIT
python3 - "$parameters_file" "$remote_script" <<'PY'
import json
import sys

path, command = sys.argv[1:]
with open(path, 'w', encoding='utf-8') as output:
    json.dump({'commands': [command], 'executionTimeout': ['1800']}, output)
PY

command_id="$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --comment "Food Rescue ${DEPLOY_MODE} ${EXPECTED_SHA:0:12}" \
    --parameters "file://$parameters_file" \
    --query 'Command.CommandId' \
    --output text)"

echo "SSM command ID: $command_id"
status="Pending"
for _ in $(seq 1 180); do
    status="$(aws ssm get-command-invocation \
        --command-id "$command_id" \
        --instance-id "$INSTANCE_ID" \
        --query 'Status' \
        --output text 2>/dev/null || true)"
    case "$status" in
        Success|Cancelled|TimedOut|Failed|Cancelling) break ;;
    esac
    sleep 10
done

stdout="$(aws ssm get-command-invocation \
    --command-id "$command_id" \
    --instance-id "$INSTANCE_ID" \
    --query 'StandardOutputContent' \
    --output text 2>/dev/null || true)"
stderr="$(aws ssm get-command-invocation \
    --command-id "$command_id" \
    --instance-id "$INSTANCE_ID" \
    --query 'StandardErrorContent' \
    --output text 2>/dev/null || true)"

[[ -z "$stdout" || "$stdout" == "None" ]] || printf '%s\n' "$stdout"
[[ -z "$stderr" || "$stderr" == "None" ]] || printf '%s\n' "$stderr" >&2

[[ "$status" == "Success" ]] || {
    echo "SSM deployment failed with status: $status" >&2
    exit 4
}
