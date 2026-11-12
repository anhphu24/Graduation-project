from __future__ import annotations

import json
import re
import sys
from pathlib import Path


EXPECTED_SUBJECT = (
    "repo:anhphu24@207956026/"
    "Graduation-project@1400940895:environment:production"
)


def load_json(root: Path, relative_path: str) -> dict:
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

    trust = load_json(root, "ops/aws/github-oidc-trust-policy.json")
    trust_statement = trust["Statement"]
    assert len(trust_statement) == 1
    trust_condition = trust_statement[0]["Condition"]["StringEquals"]
    assert trust_condition == {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": EXPECTED_SUBJECT,
    }
    assert "*" not in trust_condition["token.actions.githubusercontent.com:sub"]

    permissions = load_json(root, "ops/aws/github-actions-ssm-policy.json")
    send_command = next(
        statement
        for statement in permissions["Statement"]
        if statement.get("Sid") == "SendCommandToFoodRescueInstance"
    )
    assert send_command["Action"] == "ssm:SendCommand"
    resources = send_command["Resource"]
    assert resources == [
        "arn:aws:ec2:<AWS_REGION>:<AWS_ACCOUNT_ID>:instance/<EC2_INSTANCE_ID>",
        "arn:aws:ssm:<AWS_REGION>:<AWS_ACCOUNT_ID>:document/FoodRescueDeploy",
    ]
    assert all("AWS-RunShellScript" not in resource for resource in resources)

    read_result = next(
        statement
        for statement in permissions["Statement"]
        if statement.get("Sid") == "ReadCommandResult"
    )
    assert read_result["Action"] == ["ssm:GetCommandInvocation"]

    document = load_json(root, "ops/aws/food-rescue-deploy-document.json")
    assert document["schemaVersion"] == "2.2"
    parameters = document["parameters"]
    assert set(parameters) == {
        "ExpectedSha",
        "ExpectedMainSha",
        "DeployMode",
        "AppUser",
        "AppDir",
    }
    assert all(parameter["interpolationType"] == "ENV_VAR" for parameter in parameters.values())
    assert parameters["ExpectedSha"]["allowedPattern"] == "^[0-9a-f]{40}$"
    assert parameters["ExpectedMainSha"]["allowedPattern"] == "^[0-9a-f]{40}$"
    assert parameters["DeployMode"]["allowedValues"] == ["deploy", "rollback"]
    assert parameters["AppUser"]["allowedValues"] == ["ubuntu"]
    assert parameters["AppDir"]["allowedValues"] == ["/var/www/food-rescue"]

    workflow_texts = {
        path.name: path.read_text(encoding="utf-8")
        for path in (root / ".github/workflows").glob("*.yml")
    }
    reviewed_workflows = {
        name: text
        for name, text in workflow_texts.items()
        if name in {"ci.yml", "deploy.yml"}
    }
    assert set(reviewed_workflows) == {"ci.yml", "deploy.yml"}
    for text in reviewed_workflows.values():
        assert "ubuntu-latest" not in text
        assert "runs-on: ubuntu-24.04" in text
        for action_reference in re.findall(r"^[ \t]*uses:[ \t]*([^\s]+)", text, re.MULTILINE):
            _, separator, revision = action_reference.rpartition("@")
            assert separator == "@"
            assert re.fullmatch(r"[0-9a-f]{40}", revision), action_reference

    ci_workflow = reviewed_workflows["ci.yml"]
    assert "id-token: write" not in ci_workflow
    deploy_workflow = reviewed_workflows["deploy.yml"]
    assert "vars.DEPLOY_ENABLED == 'true'" in deploy_workflow
    assert "id-token: write" not in deploy_workflow
    assert "aws-actions/configure-aws-credentials" not in deploy_workflow
    assert "secrets.EC2_SSH_PRIVATE_KEY" in deploy_workflow
    assert "secrets.EC2_SSH_KNOWN_HOSTS" in deploy_workflow
    assert "bash scripts/ssh_deploy.sh" in deploy_workflow
    assert "needs.test.result == 'success'" in deploy_workflow

    print("Deployment security template tests passed.")


if __name__ == "__main__":
    main()
