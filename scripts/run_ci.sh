#!/usr/bin/env bash
set -euo pipefail

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test --verbosity 2

bash -n scripts/deploy_ec2.sh
bash -n scripts/ssm_deploy.sh
