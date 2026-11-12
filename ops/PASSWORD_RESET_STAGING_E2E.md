# Password reset staging E2E and log-safety plan

## Status and scope

This is a staging-only verification plan. The example Nginx policy in
[`nginx/password-reset-access-log-protection.example.conf`](nginx/password-reset-access-log-protection.example.conf)
is **not applied to production** by this repository. Do not run the mutation or
upstream-error steps on production.

The plan verifies the existing Django flow without changing its URL contract:

1. POST the customer forgot-password form over HTTPS with CSRF protection.
2. Receive the message through Resend.
3. Open the raw `uidb64/token` URL and follow Django's redirect to the
   session-backed `/set-password/` URL.
4. Set a new password, verify one-time use, and verify expiry.
5. Confirm that the raw token is absent from Nginx, Gunicorn, Django,
   journald, and centralized logs.

Use an isolated staging host, a controlled customer account, and a maintenance
window approved by the staging owner. Do not enable shell tracing (`set -x`).
Do not paste reset URLs, tokens, environment files, log lines, or passwords into
CI output, tickets, chat, or screenshots.

## 1. Read-only runtime inventory

Record the staging commit and inspect the effective runtime before applying the
example. These commands do not print environment values:

```bash
git -C /var/www/food-rescue rev-parse HEAD
git -C /var/www/food-rescue status --porcelain --untracked-files=all
sudo nginx -T
sudo systemctl cat food-rescue
sudo systemctl show food-rescue \
  --property=FragmentPath,DropInPaths,ExecStart,EnvironmentFiles,StandardOutput,StandardError \
  --no-pager
sudo systemctl is-active nginx food-rescue
```

Review `nginx -T` for all inherited and server-level `access_log`, `error_log`,
`log_format`, forwarding, and remote syslog directives. Review `ExecStart` for
Gunicorn `--access-logfile`, `--access-logformat`, `--error-logfile`,
`--capture-output`, and `--log-config` arguments. Identify journald forwarding,
log agents, APM/error-reporting SDKs, and any load balancer, CDN, or WAF in front
of Nginx. Inventory each destination, retention rule, and read permission.

Store inventory output only in the approved staging evidence location. Nginx
configuration can contain internal hostnames and certificate paths even when it
does not contain private-key material.

## 2. Integrate the example on staging

Copy the `map` from the example into the effective `http {}` context. Apply the
conditional `access_log` to every access-log destination active for the Food
Rescue `server {}`. Preserve the existing log path/format, TLS, upstream,
headers, and static-file behavior.

The example deliberately does not configure `error_log`. Nginx cannot use the
same conditional access-log mechanism to redact arbitrary error messages. The
staging owner must inspect the effective error-log behavior and choose an
operationally acceptable control for the sensitive route, such as avoiding URI
fields in the upstream logger and limiting route-specific error output. Do not
silently reduce error visibility for the rest of the application.

If Gunicorn access logging is enabled, disable it and use Nginx as the sole
access logger. If it must remain enabled, use a format that excludes the request
line, URI, query string, and Referer. A Django middleware or logging filter
cannot protect Nginx or Gunicorn access logs because those layers receive the
request before Django.

Validate and reload only on staging:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl is-active nginx food-rescue
```

## 3. Prepare safe evidence variables

Start a fresh shell. The marker is safe to print; the URL and token are not.
The token pattern file avoids placing the token in log-search command arguments.

```bash
set -euo pipefail
umask 077
AUDIT_TMP="$(mktemp -d)"
AUDIT_MARKER="food-rescue-password-reset-$(date -u +%Y%m%dT%H%M%SZ)-$$"
AUDIT_STARTED_AT="$(date --iso-8601=seconds)"
COOKIE_JAR="$AUDIT_TMP/cookies.txt"
TOKEN_PATTERN_FILE="$AUDIT_TMP/token.pattern"
trap 'rm -rf -- "$AUDIT_TMP"' EXIT
printf 'Audit marker: %s\n' "$AUDIT_MARKER"
```

Set the staging origin and controlled customer email. Do not use a production
account:

```bash
STAGING_ORIGIN='https://staging.example.invalid'
CONTROLLED_EMAIL='password-reset-staging@example.invalid'
```

## 4. CSRF negative and positive cases

Fetch the forgot-password page and retain its cookie without printing it:

```bash
FORGOT_PATH='/accounts/customer/forgot/'
curl --fail --silent --show-error \
  --user-agent "FoodRescue-Staging-E2E/$AUDIT_MARKER" \
  --cookie-jar "$COOKIE_JAR" \
  --output "$AUDIT_TMP/forgot.html" \
  "$STAGING_ORIGIN$FORGOT_PATH"
CSRF_TOKEN="$(awk '$6 == "csrftoken" { value=$7 } END { print value }' "$COOKIE_JAR")"
test -n "$CSRF_TOKEN"
```

Negative case: omit the CSRF token and require HTTP 403. Print only the result:

```bash
HTTP_STATUS="$(curl --silent --show-error \
  --user-agent "FoodRescue-Staging-E2E/$AUDIT_MARKER" \
  --cookie "$COOKIE_JAR" \
  --output /dev/null --write-out '%{http_code}' \
  --request POST \
  --data-urlencode "email=$CONTROLLED_EMAIL" \
  "$STAGING_ORIGIN$FORGOT_PATH")"
test "$HTTP_STATUS" = 403 && echo 'CSRF_NEGATIVE: PASS' || echo 'CSRF_NEGATIVE: FAIL'
```

Positive case: submit the cookie token with an HTTPS Referer and require the
redirect to the generic done page:

```bash
HTTP_STATUS="$(curl --silent --show-error \
  --user-agent "FoodRescue-Staging-E2E/$AUDIT_MARKER" \
  --cookie "$COOKIE_JAR" --cookie-jar "$COOKIE_JAR" \
  --output /dev/null --write-out '%{http_code}' \
  --request POST \
  --referer "$STAGING_ORIGIN$FORGOT_PATH" \
  --data-urlencode "email=$CONTROLLED_EMAIL" \
  --data-urlencode "csrfmiddlewaretoken=$CSRF_TOKEN" \
  "$STAGING_ORIGIN$FORGOT_PATH")"
test "$HTTP_STATUS" = 302 && echo 'CSRF_POSITIVE: PASS' || echo 'CSRF_POSITIVE: FAIL'
```

Confirm in the controlled mailbox that Resend delivered one text/HTML message,
the displayed host is the staging host, and the message states a 30-minute
expiry. Do not use Resend click tracking for this test if it rewrites the URL.

## 5. Capture the reset URL without displaying it

Paste the received URL into a hidden prompt. Validate its origin and route, then
store only the final token in a mode-0600 pattern file:

```bash
printf 'Paste the controlled reset URL (input hidden): ' >&2
IFS= read -r -s RESET_URL
printf '\n' >&2
case "$RESET_URL" in
  "$STAGING_ORIGIN"/accounts/customer/password-reset/*/*/) ;;
  *) echo 'RESET_URL_VALIDATION: FAIL'; exit 1 ;;
esac
RESET_WITHOUT_SLASH="${RESET_URL%/}"
RESET_TOKEN="${RESET_WITHOUT_SLASH##*/}"
if [[ ! "$RESET_TOKEN" =~ ^[0-9a-z]+-[0-9a-f]{32}$ ]]; then
  echo 'RESET_TOKEN_SHAPE: FAIL'
  exit 1
fi
printf '%s\n' "$RESET_TOKEN" > "$TOKEN_PATTERN_FILE"
unset RESET_TOKEN
echo 'RESET_URL_CAPTURE: PASS'
```

Never echo `RESET_URL`, source the shell with tracing enabled, or pass the token
as a literal command-line argument.

## 6. Success and single-use cases

Use a private browser profile for the normal user-facing flow. Set its User-Agent
to include the audit marker when the browser tooling permits it.

1. Open the controlled reset URL.
2. Confirm the raw URL returns a redirect and the browser ends on a URL ending
   in `/set-password/`; the raw token must no longer appear in the address bar.
3. Submit a strong staging-only password. This is the positive CSRF case for the
   confirmation form because the normal Django form supplies the cookie and
   form token.
4. Confirm redirect to the complete page and successful login with the new
   password. Confirm the old password fails.
5. In a new private profile, open the original raw URL again. Confirm the page
   reports an invalid/used link and does not show the set-password form.

Do not save the password in the evidence package. Complete the password change
before searching external logs so the controlled token is no longer usable.

## 7. Invalid-token case

Create a token-shaped invalid URL in memory without displaying it. The changed
last character preserves the Nginx map match:

```bash
RESET_WITHOUT_SLASH="${RESET_URL%/}"
LAST_CHARACTER="${RESET_WITHOUT_SLASH#${RESET_WITHOUT_SLASH%?}}"
if [ "$LAST_CHARACTER" = 0 ]; then REPLACEMENT=1; else REPLACEMENT=0; fi
INVALID_RESET_URL="${RESET_WITHOUT_SLASH%?}${REPLACEMENT}/"
unset LAST_CHARACTER REPLACEMENT
INVALID_TOKEN="${INVALID_RESET_URL%/}"
INVALID_TOKEN="${INVALID_TOKEN##*/}"
printf '%s\n' "$INVALID_TOKEN" >> "$TOKEN_PATTERN_FILE"
unset INVALID_TOKEN
HTTP_STATUS="$(curl --silent --show-error \
  --user-agent "FoodRescue-Staging-E2E/$AUDIT_MARKER-invalid" \
  --output /dev/null --write-out '%{http_code}' \
  "$INVALID_RESET_URL")"
test "$HTTP_STATUS" = 200 && echo 'INVALID_TOKEN: PASS' || echo 'INVALID_TOKEN: FAIL'
unset INVALID_RESET_URL
```

## 8. Thirty-minute expiry

First verify the effective staging value without printing settings or secrets:

```bash
sudo -u ubuntu /var/www/food-rescue/.venv/bin/python \
  /var/www/food-rescue/manage.py shell -c \
  'from django.conf import settings; raise SystemExit(0 if settings.PASSWORD_RESET_TIMEOUT == 1800 else 1)'
echo 'PASSWORD_RESET_TIMEOUT_1800: PASS'
```

Use a natural expiry: request a separate link, wait at least 1,801 seconds using
a monotonic timer, then open it and require the invalid-link page. Capture that
URL through the same hidden-input procedure in section 5 and append its final
token to `TOKEN_PATTERN_FILE` before unsetting it. Do not change the host clock.
The current repository fixes the timeout in Django settings, so an environment
only override is not valid evidence. Any accelerated strategy requires a
separately reviewed staging-only settings change and must still be recorded as a
mechanism check rather than proof of the configured 30-minute interval.

## 9. Approved upstream-error case

Run this only during an approved isolated-staging maintenance window. Use the
already invalid token-shaped URL, install a trap that restarts the application,
stop the service briefly, require a 502/503/504 from Nginx, and restart it. Do
not use an unconsumed reset token.

```bash
RESET_WITHOUT_SLASH="${RESET_URL%/}"
LAST_CHARACTER="${RESET_WITHOUT_SLASH#${RESET_WITHOUT_SLASH%?}}"
if [ "$LAST_CHARACTER" = 0 ]; then REPLACEMENT=1; else REPLACEMENT=0; fi
INVALID_RESET_URL="${RESET_WITHOUT_SLASH%?}${REPLACEMENT}/"
unset LAST_CHARACTER REPLACEMENT
# Section 7 already appended this deterministic invalid token to the protected
# pattern file. Append it again harmlessly so this section also works alone.
INVALID_TOKEN="${INVALID_RESET_URL%/}"
INVALID_TOKEN="${INVALID_TOKEN##*/}"
printf '%s\n' "$INVALID_TOKEN" >> "$TOKEN_PATTERN_FILE"
unset INVALID_TOKEN
restore_service() { sudo systemctl start food-rescue; }
trap 'restore_service; rm -rf -- "$AUDIT_TMP"' EXIT
sudo systemctl stop food-rescue
HTTP_STATUS="$(curl --silent --show-error \
  --user-agent "FoodRescue-Staging-E2E/$AUDIT_MARKER-upstream-error" \
  --output /dev/null --write-out '%{http_code}' \
  "$INVALID_RESET_URL" || true)"
case "$HTTP_STATUS" in
  502|503|504) echo 'UPSTREAM_ERROR: PASS' ;;
  *) echo 'UPSTREAM_ERROR: FAIL' ;;
esac
sudo systemctl start food-rescue
sudo systemctl is-active --quiet food-rescue
unset INVALID_RESET_URL
```

If the staging owner does not authorize a service interruption, record this case
as `NOT RUN`; do not simulate it in production.

## 10. Log-safety checks

Run searches only after the successful reset consumed the controlled token.
Every command must print only a status, never a matching line. `NOT_FOUND` is
the only passing sink result. Missing or unreadable files, an unmatched glob,
command failure, malformed collector output, and an unexecuted query must be
reported as `SCAN_ERROR` or `NOT_RUN`; neither is eligible for an overall pass.

Build `REQUIRED_SINKS` from the inventory in section 1 before running the scan.
The example assumes local Nginx access/error files and systemd journals. Add a
unique required label for every Gunicorn file, remote syslog destination,
centralized collector, APM, load balancer, CDN, and WAF found during inventory.
Do not remove a local label unless the effective configuration proves that sink
is disabled or redirects it to another required label. Preserve the
inventory-to-label mapping with the staging evidence.

```bash
test -s "$TOKEN_PATTERN_FILE" && test -r "$TOKEN_PATTERN_FILE" || {
  echo 'TOKEN_PATTERN_FILE: SCAN_ERROR'
  exit 1
}

declare -A SCAN_RESULTS=()
REQUIRED_SINKS=(
  NGINX_ACCESS
  NGINX_ERROR
  FOOD_RESCUE_JOURNAL
  NGINX_JOURNAL
  # Add GUNICORN_FILE, CENTRAL_COLLECTOR, LOAD_BALANCER, and other labels
  # discovered during inventory. A required label without a result is NOT_RUN.
)
# Change this to `yes` only after reconciling every destination from section 1
# with REQUIRED_SINKS and preserving that mapping in the evidence package.
SINK_INVENTORY_REVIEWED=no

record_scan_result() {
  local label="$1"
  local result="$2"
  case "$result" in
    FOUND|NOT_FOUND|SCAN_ERROR|NOT_RUN) ;;
    *) result=SCAN_ERROR ;;
  esac
  SCAN_RESULTS["$label"]="$result"
  printf '%s: %s\n' "$label" "$result"
}

scan_files() {
  local label="$1"
  shift
  local path
  local grep_status

  if (( $# == 0 )); then
    record_scan_result "$label" SCAN_ERROR
    return 2
  fi
  for path in "$@"; do
    if ! sudo test -f "$path" || ! sudo test -r "$path"; then
      record_scan_result "$label" SCAN_ERROR
      return 2
    fi
  done

  set +e
  sudo grep -Fq -f "$TOKEN_PATTERN_FILE" -- "$@" \
    >/dev/null 2>"$AUDIT_TMP/${label}.grep.stderr"
  grep_status=$?
  set -e
  case "$grep_status" in
    0) record_scan_result "$label" FOUND ;;
    1) record_scan_result "$label" NOT_FOUND ;;
    *) record_scan_result "$label" SCAN_ERROR; return 2 ;;
  esac
}

scan_journal() {
  local label="$1"
  local unit="$2"
  local load_state
  local output="$AUDIT_TMP/${label}.journal"
  local errors="$AUDIT_TMP/${label}.journal.stderr"

  if ! load_state="$(sudo systemctl show "$unit" --property=LoadState --value 2>"$errors")" \
    || [[ "$load_state" != loaded ]]; then
    record_scan_result "$label" SCAN_ERROR
    return 2
  fi
  if ! sudo journalctl -u "$unit" --since "$AUDIT_STARTED_AT" --no-pager \
    --output=cat >"$output" 2>"$errors"; then
    record_scan_result "$label" SCAN_ERROR
    return 2
  fi
  scan_files "$label" "$output"
}

shopt -s nullglob
NGINX_ACCESS_LOGS=(/var/log/nginx/*access*.log)
NGINX_ERROR_LOGS=(/var/log/nginx/*error*.log)
shopt -u nullglob

SCAN_COMMAND_FAILED=0
scan_files NGINX_ACCESS "${NGINX_ACCESS_LOGS[@]}" || SCAN_COMMAND_FAILED=1
scan_files NGINX_ERROR "${NGINX_ERROR_LOGS[@]}" || SCAN_COMMAND_FAILED=1
scan_journal FOOD_RESCUE_JOURNAL food-rescue || SCAN_COMMAND_FAILED=1
scan_journal NGINX_JOURNAL nginx || SCAN_COMMAND_FAILED=1
```

Add every uncompressed rotated or Gunicorn log file covering the audit window to
an inventory-derived array and call `scan_files` with its required label. A
compressed log requires a separate adapter that suppresses matching lines and
maps decompressor/search failures to `SCAN_ERROR`; do not treat it as a normal
file or omit it.

For each external collector, define an adapter that reads all token patterns
from standard input, performs an exact-token OR query without printing events,
and writes one non-negative integer count to standard output. The wrapper below
captures all output in the protected temporary directory. A missing adapter,
non-zero exit, or non-integer response cannot become `NOT_FOUND`:

```bash
scan_collector() {
  local label="$1"
  local adapter="$2"
  local count_file="$AUDIT_TMP/${label}.count"
  local errors="$AUDIT_TMP/${label}.collector.stderr"
  local query_status
  local count
  local -a count_lines=()

  if ! declare -F "$adapter" >/dev/null; then
    record_scan_result "$label" NOT_RUN
    return 2
  fi
  set +e
  "$adapter" <"$TOKEN_PATTERN_FILE" >"$count_file" 2>"$errors"
  query_status=$?
  set -e
  if (( query_status != 0 )); then
    record_scan_result "$label" SCAN_ERROR
    return 2
  fi
  if ! mapfile -t count_lines <"$count_file"; then
    record_scan_result "$label" SCAN_ERROR
    return 2
  fi
  if (( ${#count_lines[@]} != 1 )); then
    record_scan_result "$label" SCAN_ERROR
    return 2
  fi
  count="${count_lines[0]}"
  if [[ ! "$count" =~ ^[0-9]+$ ]]; then
    record_scan_result "$label" SCAN_ERROR
    return 2
  fi
  if (( count > 0 )); then
    record_scan_result "$label" FOUND
  else
    record_scan_result "$label" NOT_FOUND
  fi
}

# Example after implementing a provider-specific adapter that prints only a
# count. Add CENTRAL_COLLECTOR to REQUIRED_SINKS before running it.
# scan_collector CENTRAL_COLLECTOR query_central_collector_count \
#   || SCAN_COMMAND_FAILED=1
```

Finish with a required-sink gate. A discovered sink omitted from
`REQUIRED_SINKS` is an inventory-review failure; a required sink omitted from
execution becomes `NOT_RUN`. Only an explicit `NOT_FOUND` for every required
label produces `OVERALL_LOG_SCAN: PASS`:

```bash
OVERALL_SCAN_FAILED="$SCAN_COMMAND_FAILED"
if [[ "$SINK_INVENTORY_REVIEWED" != yes ]]; then
  echo 'REQUIRED_SINK_INVENTORY: NOT_RUN'
  OVERALL_SCAN_FAILED=1
else
  echo 'REQUIRED_SINK_INVENTORY: VERIFIED'
fi
for label in "${REQUIRED_SINKS[@]}"; do
  result="${SCAN_RESULTS[$label]:-NOT_RUN}"
  if [[ -z "${SCAN_RESULTS[$label]+present}" ]]; then
    printf '%s: NOT_RUN\n' "$label"
  fi
  if [[ "$result" != NOT_FOUND ]]; then
    OVERALL_SCAN_FAILED=1
  fi
done

if (( OVERALL_SCAN_FAILED != 0 )); then
  echo 'OVERALL_LOG_SCAN: FAIL'
  false
else
  echo 'OVERALL_LOG_SCAN: PASS'
fi
```

Record `FOUND` as a failed security check and treat the affected store as
sensitive until the controlled token has expired or been consumed and
retention/removal is handled under the staging log policy. Collector query audit
logs must not record the query token; if this cannot be established, mark that
collector `SCAN_ERROR` rather than running an unsafe query.

Search separately for the safe audit marker to correlate the test without
revealing the token. The Nginx access record for the raw-token request should be
absent, so the marker can legitimately be absent from that sink. The application
response and session redirect provide request-success evidence.

Required results:

- success/raw-token request: token `NOT_FOUND` in every sink;
- invalid token-shaped request: token `NOT_FOUND` in every sink;
- approved upstream-error request: token `NOT_FOUND` in access, error, Gunicorn,
  journal, and collector sinks;
- normal non-sensitive requests remain present in the intended access log;
- `/set-password/` remains functional and may be logged because it contains no
  raw token.

## 11. Rollback

If any functional or logging check fails:

1. Keep the application service running.
2. Restore the previous staging Nginx configuration from the approved backup.
3. Run `sudo nginx -t` before reload.
4. Run `sudo systemctl reload nginx` and verify both services are active.
5. Restore any temporary Gunicorn or `PASSWORD_RESET_TIMEOUT` setting and
   restart `food-rescue` if required.
6. Remove the temporary audit directory through the installed trap.
7. Do not promote the configuration to production. Record the check as failed
   without copying token-bearing log lines into the report.

Production promotion requires a separately reviewed change based on the actual
effective Nginx and systemd configuration plus successful staging evidence for
all available log sinks.
