#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_SHA="${EXPECTED_SHA:-}"
DEPLOY_MODE="${DEPLOY_MODE:-deploy}"
APP_DIR="${APP_DIR:-/var/www/food-rescue}"
APP_USER="${APP_USER:-ubuntu}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
ENV_FILE="${ENV_FILE:-/etc/food-rescue.env}"
SERVICE_NAME="${SERVICE_NAME:-food-rescue}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/food-rescue}"

[[ "$(id -u)" -eq 0 ]] || { echo "Deployment script must run as root." >&2; exit 10; }
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "EXPECTED_SHA must be a full commit SHA." >&2; exit 11; }
[[ "$DEPLOY_MODE" == "deploy" || "$DEPLOY_MODE" == "rollback" ]] || { echo "DEPLOY_MODE must be deploy or rollback." >&2; exit 11; }
[[ "$APP_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || { echo "Invalid APP_DIR." >&2; exit 11; }
[[ "$SERVICE_NAME" =~ ^[A-Za-z0-9@._-]+$ ]] || { echo "Invalid SERVICE_NAME." >&2; exit 11; }

for command_name in git runuser systemctl curl install getent; do
    command -v "$command_name" >/dev/null || {
        echo "Required command is unavailable: $command_name" >&2
        exit 12
    }
done

id "$APP_USER" >/dev/null
test -d "$APP_DIR/.git"
test -x "$VENV_DIR/bin/python"
test -r "$ENV_FILE"

APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"

as_app() {
    runuser -u "$APP_USER" -- env HOME="$APP_HOME" "$@"
}

git_as_app() {
    as_app git -C "$APP_DIR" "$@"
}

django_manage() {
    runuser --preserve-environment -u "$APP_USER" -- \
        env HOME="$APP_HOME" \
        "$VENV_DIR/bin/python" "$APP_DIR/manage.py" "$@"
}

DATABASE_PATH="$APP_DIR/db.sqlite3"
HEALTHCHECK_URL="http://127.0.0.1/health/"
PREVIOUS_SHA="$(git_as_app rev-parse HEAD)"
CODE_SWITCHED=0
SERVICE_STOPPED=0
SERVICE_RESTARTED=0
MIGRATIONS_STARTED=0
PRODUCTION_ENV_LOADED=0
DATABASE_BACKUP=""
DATABASE_UID=""
DATABASE_GID=""
DATABASE_MODE=""

restore_previous_release() {
    local original_exit="$1"
    trap - ERR
    echo "Deployment failed; restoring the previous code release." >&2

    if [[ "$CODE_SWITCHED" -eq 1 ]]; then
        git_as_app switch --detach "$PREVIOUS_SHA" || true
        if [[ -f "$APP_DIR/requirements.txt" ]]; then
            as_app "$VENV_DIR/bin/python" -m pip install \
                --disable-pip-version-check -r "$APP_DIR/requirements.txt" || true
        fi
        if [[ "$PRODUCTION_ENV_LOADED" -eq 1 ]]; then
            django_manage collectstatic --noinput || true
        fi
    fi

    if [[ "$SERVICE_STOPPED" -eq 1 && "$SERVICE_RESTARTED" -eq 0 && -n "$DATABASE_BACKUP" ]]; then
        install -o "$DATABASE_UID" -g "$DATABASE_GID" -m "$DATABASE_MODE" \
            "$DATABASE_BACKUP" "$DATABASE_PATH" || true
        echo "SQLite database restored because the service was never restarted." >&2
    elif [[ "$MIGRATIONS_STARTED" -eq 1 && -n "$DATABASE_BACKUP" ]]; then
        echo "SQLite backup retained at $DATABASE_BACKUP; it was not restored automatically after restart." >&2
    fi

    if [[ "$SERVICE_STOPPED" -eq 1 || "$SERVICE_RESTARTED" -eq 1 ]]; then
        systemctl restart "$SERVICE_NAME" || true
    fi
    exit "$original_exit"
}

trap 'restore_previous_release $?' ERR

[[ -z "$(git_as_app status --porcelain --untracked-files=all)" ]] || {
    echo "EC2 working tree is not clean." >&2
    exit 20
}

git_as_app fetch --no-tags origin main
ORIGIN_MAIN="$(git_as_app rev-parse refs/remotes/origin/main)"

if [[ "$DEPLOY_MODE" == "deploy" ]]; then
    [[ "$EXPECTED_SHA" == "$ORIGIN_MAIN" ]] || {
        echo "EXPECTED_SHA does not match origin/main." >&2
        exit 21
    }
else
    git_as_app merge-base --is-ancestor "$EXPECTED_SHA" "$ORIGIN_MAIN" || {
        echo "Rollback target is not in origin/main history." >&2
        exit 22
    }
fi

git_as_app cat-file -e "${EXPECTED_SHA}^{commit}"
git_as_app switch --detach "$EXPECTED_SHA"
CODE_SWITCHED=1
[[ "$(git_as_app rev-parse HEAD)" == "$EXPECTED_SHA" ]]

as_app "$VENV_DIR/bin/python" -m pip install \
    --disable-pip-version-check -r "$APP_DIR/requirements.txt"

# Export production values only to child processes. Deployment control values
# are restored immediately so /etc/food-rescue.env cannot change the target.
readonly deploy_expected_sha="$EXPECTED_SHA"
readonly deploy_mode="$DEPLOY_MODE"
readonly deploy_app_dir="$APP_DIR"
readonly deploy_app_user="$APP_USER"
readonly deploy_venv_dir="$VENV_DIR"
readonly deploy_env_file="$ENV_FILE"
readonly deploy_service_name="$SERVICE_NAME"
readonly deploy_backup_dir="$BACKUP_DIR"
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
PRODUCTION_ENV_LOADED=1
EXPECTED_SHA="$deploy_expected_sha"
DEPLOY_MODE="$deploy_mode"
APP_DIR="$deploy_app_dir"
APP_USER="$deploy_app_user"
VENV_DIR="$deploy_venv_dir"
ENV_FILE="$deploy_env_file"
SERVICE_NAME="$deploy_service_name"
BACKUP_DIR="$deploy_backup_dir"
DATABASE_PATH="${DJANGO_DATABASE_PATH:-$APP_DIR/db.sqlite3}"
HEALTHCHECK_URL="${DEPLOY_HEALTHCHECK_URL:-http://127.0.0.1/health/}"

django_manage check --deploy --fail-level WARNING

systemctl stop "$SERVICE_NAME"
SERVICE_STOPPED=1

test -f "$DATABASE_PATH"
DATABASE_UID="$(stat -c '%u' "$DATABASE_PATH")"
DATABASE_GID="$(stat -c '%g' "$DATABASE_PATH")"
DATABASE_MODE="$(stat -c '%a' "$DATABASE_PATH")"
install -d -m 0750 "$BACKUP_DIR"
DATABASE_BACKUP="$BACKUP_DIR/db-$(date -u +%Y%m%dT%H%M%SZ)-${PREVIOUS_SHA:0:12}.sqlite3"
"$VENV_DIR/bin/python" - "$DATABASE_PATH" "$DATABASE_BACKUP" <<'PY'
import sqlite3
import sys

source_path, backup_path = sys.argv[1:]
with sqlite3.connect(source_path) as source, sqlite3.connect(backup_path) as backup:
    source.backup(backup)
PY
chmod 0640 "$DATABASE_BACKUP"
echo "SQLite backup created: $DATABASE_BACKUP"

if [[ "$DEPLOY_MODE" == "deploy" ]]; then
    MIGRATIONS_STARTED=1
    django_manage migrate --noinput
fi

django_manage collectstatic --noinput
systemctl restart "$SERVICE_NAME"
SERVICE_RESTARTED=1
systemctl is-active --quiet "$SERVICE_NAME"

curl --fail --silent --show-error \
    --retry 10 --retry-delay 3 --retry-all-errors \
    --max-time 10 "$HEALTHCHECK_URL" >/dev/null

DEPLOYED_SHA="$(git_as_app rev-parse HEAD)"
[[ "$DEPLOYED_SHA" == "$EXPECTED_SHA" ]] || {
    echo "Deployed SHA does not match EXPECTED_SHA." >&2
    restore_previous_release 30
}

trap - ERR
echo "Deployment successful: $DEPLOYED_SHA"
