# Food Rescue: GitHub Actions → SSH → EC2

## Architecture and scope

The AWS VocLabs session does not permit IAM role creation (`iam:CreateRole` denied). Therefore the deployment transport is **SSH**, not OIDC or SSM. The existing Django CI, exact commit selection, SQLite backup, migrations, service restart, health checks, and rollback remain.

- Repository: `anhphu24/Graduation-project`
- Protected branch: `main`
- EC2 application path: `/var/www/food-rescue`
- EC2 application user: `ubuntu`
- systemd service: `food-rescue`
- SSH deployment is deliberately disabled until `DEPLOY_ENABLED=true` is set as a repository variable.
- No AWS credentials or IAM role are required by the SSH workflow.

## 1. Verify server prerequisites (read-only)

On EC2:

```bash
sudo systemctl is-active food-rescue nginx
sudo -u ubuntu git -C /var/www/food-rescue status --porcelain --untracked-files=all
sudo -u ubuntu git -C /var/www/food-rescue rev-parse HEAD
sudo test -f /etc/food-rescue.env && echo "env exists"
sudo test -x /var/www/food-rescue/.venv/bin/python && echo "venv exists"
sudo -n true && echo "non-interactive sudo available"
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Working tree must be empty. Do not print the production `.env` or database.

## 2. SSH key dedicated to GitHub deployment

On your TRUSTED local Windows computer (PowerShell), generate a dedicated key:

```powershell
ssh-keygen -t ed25519 -a 100 -f "$HOME\.ssh\food-rescue-actions" -C "food-rescue-github-actions"
```

The runner uses a non-interactive key, so create it without a passphrase and restrict its purpose. Keep the private key off the repository. An unencrypted CI key is highly sensitive; use an environment approval gate, rotate on exposure, and restrict who can edit workflows.

Append ONLY the contents of `food-rescue-actions.pub` as a single line in `/home/ubuntu/.ssh/authorized_keys` on EC2, preserving existing keys. Set directory mode 700, file mode 600 and ubuntu ownership. Test from your local computer using `ssh -i ... ubuntu@HOST` **before** enabling the workflow.

Your existing EC2 SSH login key should not be reused as a GitHub secret.

## 3. Pin EC2 host identity

On the EC2 itself, inspect the SSH host public key:

```bash
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Record and independently verify the public key/fingerprint through the existing trusted SSH session. In a known_hosts line, use the EC2 public IP/DNS name and this exact public key:

```text
HOSTNAME ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... 
```

For port other than 22, use `[HOSTNAME]:PORT ssh-ed25519 ...`. Do not blindly trust an unauthenticated `ssh-keyscan` result.

## 4. GitHub configuration

At Settings → Environments, create `production`, restrict deployment branches to `main`, and configure reviewers if your plan/repository supports them. Protect `main` with PR and `Django tests` rules.

At Settings → Secrets and variables → Actions:

**Repository variables** (or environment variables except the deploy gate):

- `EC2_SSH_HOST`: verified EC2 public IP or DNS name (DuckDNS is usable only when updated to the current IP)
- `EC2_SSH_PORT`: usually `22`
- `PRODUCTION_HEALTHCHECK_URL`: `https://YOUR-DOMAIN/health/` (publicly accessible over valid HTTPS)
- `PRODUCTION_ROLLBACK_HEALTHCHECK_URL`: `https://YOUR-DOMAIN/` (older baseline)
- `DEPLOY_ENABLED`: unset / `false` during setup (must be a **repository variable**, not only environment-scoped, because job condition evaluates before entering environment)

**production environment secrets**:

- `EC2_SSH_PRIVATE_KEY`: exact private OpenSSH key text from dedicated key
- `EC2_SSH_KNOWN_HOSTS`: verified single-line host public key binding in OpenSSH known_hosts format

Never paste either secret into chat, issues, logs, pull requests or source files. `EC2_SSH_KNOWN_HOSTS` is not itself confidential, but store it as a secret to protect workflow configuration from accidental exposure.

## 5. SSH access and network reality

Port 22 ingress on the EC2 Security Group must be reachable from the runner. Standard GitHub-hosted runner IPs are dynamic and broad; **do not open 22 to 0.0.0.0/0 merely to make CI work**. GitHub does not recommend ordinary hosted runners for security-group IP allowlists. Prefer a self-hosted runner on a trusted machine/network with a fixed outgoing IP or GitHub-hosted larger runner with static IP where available. Alternatively use an approved narrow temporary allowlist with explicit expiration and audit, acknowledging that rotating runner IPs may break deployments.

For a self-hosted runner, be careful: its host is trusted to execute repository workflows and must not run untrusted PR code with deployment credentials. Keep deploy jobs on protected branches/environments only.

## 6. Deployment behavior

- PR → CI tests.
- push to main → resolve exact SHA → test candidate and tooling.
- deploy job is **skipped** unless repository variable `DEPLOY_ENABLED=true`.
- Workflow checks out the reviewed main tooling SHA.
- `ssh_deploy.sh` requires a pinned host key, dedicated SSH key, `ubuntu`, and non-interactive sudo. The reviewed `deploy_ec2.sh` is streamed over SSH to `sudo /bin/bash -s`.
- Server confirms clean Git tree and exact `origin/main` SHA, then deploys or rolls back only to an ancestor of main.
- Backup SQLite → migration when deploy → collectstatic → restart systemd → health check.
- Rollback of code does **not** automatically reverse migrations; test backup/restore on a staging copy before first production deploy.

**Security note:** Current `ubuntu` has sudo for the streamed script. It is a powerful credential on the EC2. A dedicated restricted deployment account and server-side root-owned wrapper would reduce risk, but requires further server setup; avoid granting this key to untrusted workflows.

## 7. First production deployment

1. Merge the SSH transport PR only after CI passes.
2. Verify authentication + host key manually from an isolated local test, and verify the server's read-only baseline.
3. Verify backup/restore on a copy of SQLite and production HTTPS health endpoint.
4. Ensure `production` environment and branch protections exist.
5. Only then set the repository variable `DEPLOY_ENABLED=true`.
6. Actions → **Deploy production** → Run workflow → branch `main` → operation `deploy`. Approve environment if required.
7. Confirm workflow success, `food-rescue` and `nginx` active, public `/health/` returns HTTP 200, and EC2 SHA equals the recorded target.
8. Consider resetting `DEPLOY_ENABLED=false` after the initial controlled deployment until ready for automatic deployments.

Do not run any AWS IAM/SSM creation commands for this SSH route. Files under `ops/aws/` and `scripts/ssm_deploy.sh` are retained as historical alternatives but are **not called** by active CI/CD.
