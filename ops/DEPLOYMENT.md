# Food Rescue production deployment

本番環境は `main` の検証済みコミットだけを、GitHub OIDC と AWS Systems Manager Run Command で EC2 に反映します。SSH 秘密鍵と長期 AWS アクセスキーは GitHub に保存しません。

## 現在の安全状態

- 安定版 baseline: `2eac2aed255ed389d7a2a0ca06bedaf841827393`
- `DEPLOY_ENABLED` が未設定または `true` 以外の場合、deploy job は実行されません。
- CI/CD のレビュー中は `DEPLOY_ENABLED` を作成しないでください。
- workflow のテスト job は SQLite の一時 test database だけを使用し、本番 database へ接続しません。

## AWS prerequisites

1. EC2 に SSM Agent を導入し、instance profile に `AmazonSSMManagedInstanceCore` を付与します。
2. GitHub 用 OIDC provider `token.actions.githubusercontent.com` を IAM に作成し、audience を `sts.amazonaws.com` にします。
3. [`aws/github-oidc-trust-policy.json`](aws/github-oidc-trust-policy.json) の placeholder を置換して deploy role の trust policy に設定します。
4. [`aws/github-actions-ssm-policy.json`](aws/github-actions-ssm-policy.json) の placeholder を置換し、deploy role に付与します。
5. EC2 の repository が `main` を取得できる read-only GitHub deploy key を使用します。GitHub Actions 用の SSH key は不要です。
6. `/etc/food-rescue.env` は root 管理とし、repository に commit しません。必要な項目は [`.env.example`](../.env.example) を参照します。

## GitHub environment and variables

GitHub の `Settings > Environments` で `production` environment を作成し、可能であれば required reviewer と deployment branch `main` を設定します。`DEPLOY_ENABLED` は job 開始前の gate で参照するため repository variable にし、それ以外は repository または `production` environment variables に登録します。

| Variable | 内容 |
|---|---|
| `AWS_REGION` | EC2 と SSM を使用する AWS region |
| `AWS_ROLE_TO_ASSUME` | GitHub OIDC が引き受ける IAM role ARN |
| `EC2_INSTANCE_ID` | 対象 EC2 instance ID |
| `EC2_APP_USER` | repository と virtualenv の所有者。未設定時は `ubuntu` |
| `PRODUCTION_HEALTHCHECK_URL` | 公開 `/health/` URL |
| `DEPLOY_ENABLED` | 最終テストと承認後にだけ `true` を設定 |

AWS access key、secret access key、SSH private key は登録しません。OIDC の trust policy は `production` environment の subject に限定されています。

## GitHub ruleset for main

`Settings > Rules > Rulesets` で `main` を対象に active ruleset を作成します。

- Require a pull request before merging
- Require one approval（単独開発で reviewer を用意できない場合は 0 にし、PR 自体は必須にする）
- Dismiss stale approvals
- Require status checks: `Django tests`
- Require conversation resolution
- Block force pushes and branch deletion
- Bypass は原則設定しない

## Deployment sequence

`main` 更新後、workflow は test、対象 SHA の確定、OIDC 認証、SSM Run Command の順に実行します。EC2 script は clean working tree と `origin/main` を再確認し、対象 commit に detached HEAD で切り替えます。`git reset --hard` と `git clean` は使用しません。

本番 check が成功した後に service を停止し、SQLite online-backup API で `/var/backups/food-rescue` に backup を作成します。その後 migration、collectstatic、service restart、local health check、commit SHA 確認を行います。`db.sqlite3`、`media/`、`/etc/food-rescue.env` は Git の更新対象外です。

## Rollback

Actions の `Deploy production` を手動実行し、`operation=rollback` と `main` 履歴内の full commit SHA を指定します。rollback は code と dependencies を対象とし、reverse migration を自動実行しません。

Migration 後、service restart 前に失敗した場合だけ、script は直前の SQLite backup を自動復元します。service を一度 restart した後は新しい書き込みを失う可能性があるため database を自動復元しません。backup path を log に残し、停止時間と data 差分を確認してから手動復元します。

## Phase 1 verification

```bash
bash -n scripts/deploy_ec2.sh
bash -n scripts/ssm_deploy.sh
bash scripts/run_ci.sh
```

Phase 1 では workflow file の review と CI 成功を確認します。`DEPLOY_ENABLED` は設定せず、SSM command と production deployment は実行しません。
