#!/usr/bin/env python3
"""Static regression checks for the GitHub Actions -> SSH deployment route."""
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
workflow = (root / ".github/workflows/deploy.yml").read_text()
script = (root / "scripts/ssh_deploy.sh").read_text()

required_workflow = (
    "vars.DEPLOY_ENABLED == 'true'",
    "needs.test.result == 'success'",
    "needs.resolve-target.result == 'success'",
    "environment:",
    "name: production",
    "secrets.EC2_SSH_PRIVATE_KEY",
    "secrets.EC2_SSH_KNOWN_HOSTS",
    "needs.resolve-target.outputs.main_sha",
    "bash scripts/ssh_deploy.sh",
)
required_script = (
    "StrictHostKeyChecking=yes",
    "BatchMode=yes",
    "IdentitiesOnly=yes",
    "ForwardAgent=no",
    "ClearAllForwardings=yes",
    "sudo -n",
    "EXPECTED_SHA=",
    "EXPECTED_MAIN_SHA=",
    "/bin/bash -s",
    "ssh-keygen -F",
)
for value in required_workflow:
    assert value in workflow, f"Missing safe workflow condition: {value}"
for value in required_script:
    assert value in script, f"Missing SSH security control: {value}"
assert "aws-actions/configure-aws-credentials" not in workflow
assert "scripts/ssm_deploy.sh" not in workflow
assert "StrictHostKeyChecking=no" not in script
assert "ssh-keyscan" not in script
print("PASS: SSH workflow security checks")
