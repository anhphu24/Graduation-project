#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="."
MODE="all"

while (($#)); do
    case "$1" in
        --project-root) PROJECT_ROOT="${2:-}"; shift 2 ;;
        --django-only) MODE="django"; shift ;;
        --deployment-only) MODE="deployment"; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done

[[ -d "$PROJECT_ROOT" ]] || { echo "Project root does not exist: $PROJECT_ROOT" >&2; exit 2; }
PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"

if [[ "$MODE" == "all" || "$MODE" == "django" ]]; then
    (
        cd "$PROJECT_ROOT"
        python manage.py check
        python manage.py makemigrations --check --dry-run
        python manage.py test --verbosity 2
    )
fi

if [[ "$MODE" == "all" || "$MODE" == "deployment" ]]; then
    bash -n "$PROJECT_ROOT/scripts/deploy_ec2.sh"
    bash -n "$PROJECT_ROOT/scripts/ssh_deploy.sh"
    bash -n "$PROJECT_ROOT/scripts/resolve_deploy_target.sh"
    bash -n "$PROJECT_ROOT/scripts/tests/test_resolve_deploy_target.sh"
    bash "$PROJECT_ROOT/scripts/tests/test_resolve_deploy_target.sh" "$PROJECT_ROOT"
    python "$PROJECT_ROOT/scripts/tests/test_ssh_security.py" "$PROJECT_ROOT"
fi
