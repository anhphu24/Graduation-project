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
3. [`aws/food-rescue-deploy-document.json`](aws/food-rescue-deploy-document.json) を `FoodRescueDeploy` という customer-managed Command document として作成します。汎用の `AWS-RunShellScript` を deploy role から呼び出さないでください。
4. [`aws/github-oidc-trust-policy.json`](aws/github-oidc-trust-policy.json) の AWS account placeholder を置換して deploy role の trust policy に設定します。
5. [`aws/github-actions-ssm-policy.json`](aws/github-actions-ssm-policy.json) の placeholder を置換し、deploy role に付与します。この policy は対象 EC2 と `FoodRescueDeploy` document だけに `ssm:SendCommand` を許可します。
6. EC2 の repository が `main` を取得できる read-only GitHub deploy key を使用します。GitHub Actions 用の SSH key は不要です。
7. `/etc/food-rescue.env` は root 管理とし、repository に commit しません。必要な項目は [`.env.example`](../.env.example) を参照します。

`DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=1` と `DJANGO_SECURE_HSTS_PRELOAD=1` は、対象 domain の全 subdomain が HTTPS のみで提供されることを確認してから使用します。条件を満たさない場合は値を下げるだけではなく、`check --deploy --fail-level WARNING` の警告を review して運用方針を決めてください。

SSM document の作成は AWS 管理者が内容を review した後に手動で行います。Phase 1 では実行しません。

```bash
aws ssm create-document \
  --name FoodRescueDeploy \
  --document-type Command \
  --document-format JSON \
  --content file://ops/aws/food-rescue-deploy-document.json
```

document は `interpolationType=ENV_VAR`、`allowedPattern`、`allowedValues` で入力を制限します。`AppUser=ubuntu` と `AppDir=/var/www/food-rescue` も固定し、別の user や path を指定できません。EC2 の SSM Agent は environment variable interpolation に対応する `3.3.2746.0` 以降を使用してください。古い Agent 向け fallback も含まれますが、更新済み Agent を前提に検証します。

## Verified GitHub OIDC identity

2026-11-04 に public GitHub REST API から次を read-only で確認しました。

- repository: `anhphu24/Graduation-project`
- repository ID: `1400940895`
- owner ID: `207956026`
- repository OIDC configuration: `use_default=true`, `use_immutable_subject=true`
- production environment subject: `repo:anhphu24@207956026/Graduation-project@1400940895:environment:production`

Trust policy は上記 subject と audience `sts.amazonaws.com` の完全一致だけを許可します。repository の OIDC customization を変更した場合は、IAM role を変更する前に subject を再確認してください。OIDC token 自体を log に出力しないでください。

## GitHub environment and variables

GitHub の `Settings > Environments` で `production` environment を作成し、可能であれば required reviewer と deployment branch `main` を設定します。`DEPLOY_ENABLED` は job 開始前の gate で参照するため repository variable にし、それ以外は repository または `production` environment variables に登録します。

| Variable | 内容 |
|---|---|
| `AWS_REGION` | EC2 と SSM を使用する AWS region |
| `AWS_ROLE_TO_ASSUME` | GitHub OIDC が引き受ける IAM role ARN |
| `EC2_INSTANCE_ID` | 対象 EC2 instance ID |
| `PRODUCTION_HEALTHCHECK_URL` | 公開 `/health/` URL |
| `PRODUCTION_ROLLBACK_HEALTHCHECK_URL` | rollback 対象にも存在する公開 URL。初期 baseline では `/` を使用 |
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

`main` 更新後、workflow は対象 SHA の確定、対象 SHA の test、OIDC 認証、SSM Run Command の順に実行します。rollback でも指定した SHA を checkout し、Django check、migration check、unit tests が成功しなければ deploy job は実行されません。deployment tooling は同時に確定した `origin/main` の SHA から取得して検証します。workflow の検証後に `origin/main` が変化した場合、EC2 側は deploy を拒否するため、未検証の新しい tooling が途中で使われることはありません。

EC2 script は clean working tree と `origin/main` を再確認し、対象 commit に detached HEAD で切り替えます。`git reset --hard` と `git clean` は使用しません。

本番 check が成功した後に service を停止し、SQLite online-backup API で `/var/backups/food-rescue` に backup を作成します。その後 migration、collectstatic、service restart、local health check、commit SHA 確認を行います。`db.sqlite3`、`media/`、`/etc/food-rescue.env` は Git の更新対象外です。

## Rollback

Actions の `Deploy production` を手動実行し、`operation=rollback` と `main` 履歴内の full commit SHA を指定します。rollback は code と dependencies を対象とし、reverse migration を自動実行しません。初期 baseline には `/health/` が存在しないため、rollback の local/public health check は `/` を使用します。

Migration 後、service restart 前に失敗した場合だけ、script は integrity check 済みの SQLite backup を自動復元します。service を一度 restart した後は新しい書き込みを失う可能性があるため database を自動復元しません。この場合は exit code `40` で automatic rollback incomplete と報告し、成功扱いにしません。backup path を log に残し、停止時間と data 差分を確認してから手動復元します。

## Phase 1 verification

```bash
bash -n scripts/deploy_ec2.sh
bash -n scripts/ssm_deploy.sh
bash -n scripts/resolve_deploy_target.sh
bash scripts/tests/test_resolve_deploy_target.sh
bash scripts/tests/test_ssm_deploy.sh
bash scripts/run_ci.sh
```

Phase 1 では workflow file の review と CI 成功を確認します。`DEPLOY_ENABLED` は設定せず、SSM command と production deployment は実行しません。
