#!/usr/bin/env bash
set -euo pipefail

INSTANCE_ID=""
DOCUMENT_NAME="FoodRescueDeploy"
APP_USER="ubuntu"
APP_DIR="/var/www/food-rescue"
EXPECTED_SHA=""
EXPECTED_MAIN_SHA=""
DEPLOY_MODE="deploy"

while (($#)); do
    case "$1" in
        --instance-id) INSTANCE_ID="${2:-}"; shift 2 ;;
        --document-name) DOCUMENT_NAME="${2:-}"; shift 2 ;;
        --app-user) APP_USER="${2:-}"; shift 2 ;;
        --app-dir) APP_DIR="${2:-}"; shift 2 ;;
        --expected-sha) EXPECTED_SHA="${2:-}"; shift 2 ;;
        --expected-main-sha) EXPECTED_MAIN_SHA="${2:-}"; shift 2 ;;
        --mode) DEPLOY_MODE="${2:-}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

[[ "$INSTANCE_ID" =~ ^i-[0-9a-f]+$ ]] || { echo "Invalid EC2 instance ID." >&2; exit 2; }
[[ "$DOCUMENT_NAME" =~ ^[A-Za-z0-9_.-]{3,128}$ ]] || { echo "Invalid SSM document name." >&2; exit 2; }
[[ "$APP_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "Invalid EC2 app user." >&2; exit 2; }
[[ "$APP_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || { echo "Invalid EC2 app directory." >&2; exit 2; }
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Expected SHA must contain 40 lowercase hex characters." >&2; exit 2; }
[[ "$EXPECTED_MAIN_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Expected main SHA must contain 40 lowercase hex characters." >&2; exit 2; }
[[ "$DEPLOY_MODE" == "deploy" || "$DEPLOY_MODE" == "rollback" ]] || { echo "Mode must be deploy or rollback." >&2; exit 2; }

for command_name in aws python3; do
    command -v "$command_name" >/dev/null || {
        echo "Required command is unavailable: $command_name" >&2
        exit 3
    }
done

parameters_file="$(mktemp)"
trap 'rm -f "$parameters_file"' EXIT
python3 - "$parameters_file" "$EXPECTED_SHA" "$EXPECTED_MAIN_SHA" "$DEPLOY_MODE" "$APP_USER" "$APP_DIR" <<'PY'
import json
import sys

path, expected_sha, expected_main_sha, deploy_mode, app_user, app_dir = sys.argv[1:]
with open(path, 'w', encoding='utf-8') as output:
    json.dump(
        {
            'ExpectedSha': [expected_sha],
            'ExpectedMainSha': [expected_main_sha],
            'DeployMode': [deploy_mode],
            'AppUser': [app_user],
            'AppDir': [app_dir],
        },
        output,
    )
PY

command_id="$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "$DOCUMENT_NAME" \
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
