#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RESOLVER="$PROJECT_ROOT/scripts/resolve_deploy_target.sh"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

git init --bare "$TEST_ROOT/remote.git" >/dev/null
git init "$TEST_ROOT/work" >/dev/null
git -C "$TEST_ROOT/work" config user.name "CI Test"
git -C "$TEST_ROOT/work" config user.email "ci-test@example.invalid"
git -C "$TEST_ROOT/work" checkout -b main >/dev/null
git -C "$TEST_ROOT/work" remote add origin "$TEST_ROOT/remote.git"

echo "first" > "$TEST_ROOT/work/release.txt"
git -C "$TEST_ROOT/work" add release.txt
git -C "$TEST_ROOT/work" commit -m "first" >/dev/null
first_sha="$(git -C "$TEST_ROOT/work" rev-parse HEAD)"
git -C "$TEST_ROOT/work" push -u origin main >/dev/null

echo "second" > "$TEST_ROOT/work/release.txt"
git -C "$TEST_ROOT/work" commit -am "second" >/dev/null
main_sha="$(git -C "$TEST_ROOT/work" rev-parse HEAD)"
git -C "$TEST_ROOT/work" push origin main >/dev/null
git -C "$TEST_ROOT/work" fetch --no-tags origin main >/dev/null

assert_output() {
    local expected_mode="$1"
    local expected_sha="$2"
    local output_file="$3"
    grep -Fxq "mode=$expected_mode" "$output_file"
    grep -Fxq "sha=$expected_sha" "$output_file"
    grep -Fxq "main_sha=$main_sha" "$output_file"
}

run_success() {
    local event_name="$1"
    local requested_mode="$2"
    local requested_sha="$3"
    local push_sha="$4"
    local expected_mode="$5"
    local expected_sha="$6"
    local output_file="$TEST_ROOT/output"
    : > "$output_file"
    (
        cd "$TEST_ROOT/work"
        EVENT_NAME="$event_name" \
        REQUESTED_MODE="$requested_mode" \
        REQUESTED_SHA="$requested_sha" \
        PUSH_SHA="$push_sha" \
        GITHUB_OUTPUT="$output_file" \
        bash "$RESOLVER" >/dev/null
    )
    assert_output "$expected_mode" "$expected_sha" "$output_file"
}

run_failure() {
    local event_name="$1"
    local requested_mode="$2"
    local requested_sha="$3"
    local push_sha="$4"
    if (
        cd "$TEST_ROOT/work"
        EVENT_NAME="$event_name" \
        REQUESTED_MODE="$requested_mode" \
        REQUESTED_SHA="$requested_sha" \
        PUSH_SHA="$push_sha" \
        bash "$RESOLVER" >/dev/null 2>&1
    ); then
        echo "Expected target resolution to fail." >&2
        exit 1
    fi
}

run_success push "" "" "$main_sha" deploy "$main_sha"
run_success workflow_dispatch deploy "" "" deploy "$main_sha"
run_success workflow_dispatch rollback "$first_sha" "" rollback "$first_sha"
run_failure push "" "" "$first_sha"
run_failure workflow_dispatch rollback deadbeef ""
run_failure workflow_dispatch unsupported "" ""

git -C "$TEST_ROOT/work" checkout --orphan unrelated >/dev/null
git -C "$TEST_ROOT/work" rm -rf . >/dev/null
echo "unrelated" > "$TEST_ROOT/work/unrelated.txt"
git -C "$TEST_ROOT/work" add unrelated.txt
git -C "$TEST_ROOT/work" commit -m "unrelated" >/dev/null
unrelated_sha="$(git -C "$TEST_ROOT/work" rev-parse HEAD)"
run_failure workflow_dispatch rollback "$unrelated_sha" ""

echo "Deployment target resolution tests passed."
