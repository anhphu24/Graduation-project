#!/usr/bin/env bash
set -euo pipefail

EVENT_NAME="${EVENT_NAME:-}"
REQUESTED_MODE="${REQUESTED_MODE:-}"
REQUESTED_SHA="${REQUESTED_SHA:-}"
PUSH_SHA="${PUSH_SHA:-}"
GITHUB_OUTPUT="${GITHUB_OUTPUT:-}"
MAIN_REF="${MAIN_REF:-refs/remotes/origin/main}"

full_sha_pattern='^[0-9a-f]{40}$'
origin_main="$(git rev-parse "${MAIN_REF}^{commit}")"
[[ "$origin_main" =~ $full_sha_pattern ]] || {
    echo "Unable to resolve origin/main to a full commit SHA." >&2
    exit 2
}

case "$EVENT_NAME" in
    push)
        mode="deploy"
        target="$PUSH_SHA"
        [[ "$target" =~ $full_sha_pattern ]] || {
            echo "Push deployment requires a full 40-character commit SHA." >&2
            exit 2
        }
        [[ "$target" == "$origin_main" ]] || {
            echo "Push SHA does not match origin/main." >&2
            exit 2
        }
        ;;
    workflow_dispatch)
        case "$REQUESTED_MODE" in
            deploy|"")
                mode="deploy"
                target="$origin_main"
                ;;
            rollback)
                mode="rollback"
                target="$REQUESTED_SHA"
                [[ "$target" =~ $full_sha_pattern ]] || {
                    echo "Rollback requires a full 40-character commit SHA." >&2
                    exit 2
                }
                ;;
            *)
                echo "Unsupported deployment operation: $REQUESTED_MODE" >&2
                exit 2
                ;;
        esac
        ;;
    *)
        echo "Unsupported workflow event: $EVENT_NAME" >&2
        exit 2
        ;;
esac

git cat-file -e "${target}^{commit}" 2>/dev/null || {
    echo "Selected target is not an available commit." >&2
    exit 2
}
git merge-base --is-ancestor "$target" "$origin_main" || {
    echo "Selected target is not in origin/main history." >&2
    exit 2
}

if [[ -n "$GITHUB_OUTPUT" ]]; then
    {
        echo "mode=$mode"
        echo "sha=$target"
        echo "main_sha=$origin_main"
    } >> "$GITHUB_OUTPUT"
fi

echo "Selected $mode target: $target"
