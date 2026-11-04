#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT
CAPTURE_FILE="$TEST_ROOT/parameters.json"

cat > "$TEST_ROOT/aws" <<'AWS'
#!/usr/bin/env bash
set -euo pipefail

if [[ "$1" == "ssm" && "$2" == "send-command" ]]; then
    shift 2
    document_name=""
    parameters=""
    while (($#)); do
        case "$1" in
            --document-name) document_name="$2"; shift 2 ;;
            --parameters) parameters="$2"; shift 2 ;;
            *) shift ;;
        esac
    done
    [[ "$document_name" == "FoodRescueDeploy" ]]
    cp "${parameters#file://}" "$CAPTURE_FILE"
    echo "command-test-123"
elif [[ "$1" == "ssm" && "$2" == "get-command-invocation" ]]; then
    case "$*" in
        *"--query Status "*) echo "Success" ;;
        *) echo "None" ;;
    esac
else
    echo "Unexpected fake AWS CLI invocation: $*" >&2
    exit 1
fi
AWS
chmod 0700 "$TEST_ROOT/aws"

cat > "$TEST_ROOT/python3" <<'PYTHON'
#!/usr/bin/env bash
exec python "$@"
PYTHON
chmod 0700 "$TEST_ROOT/python3"

expected_sha="$(printf 'a%.0s' {1..40})"
expected_main_sha="$(printf 'b%.0s' {1..40})"
PATH="$TEST_ROOT:$PATH" CAPTURE_FILE="$CAPTURE_FILE" \
    MSYS2_ARG_CONV_EXCL='/var/www/food-rescue' \
    bash "$PROJECT_ROOT/scripts/ssm_deploy.sh" \
        --instance-id i-0123456789abcdef0 \
        --document-name FoodRescueDeploy \
        --app-user ubuntu \
        --app-dir /var/www/food-rescue \
        --expected-sha "$expected_sha" \
        --expected-main-sha "$expected_main_sha" \
        --mode rollback >/dev/null

python - "$CAPTURE_FILE" "$expected_sha" "$expected_main_sha" <<'PY'
import json
import sys

path, expected_sha, expected_main_sha = sys.argv[1:]
with open(path, encoding="utf-8") as source:
    parameters = json.load(source)

expected = {
    "ExpectedSha": [expected_sha],
    "ExpectedMainSha": [expected_main_sha],
    "DeployMode": ["rollback"],
    "AppUser": ["ubuntu"],
    "AppDir": ["/var/www/food-rescue"],
}
assert parameters == expected, parameters
assert "commands" not in parameters
PY

echo "SSM deployment wrapper tests passed."
