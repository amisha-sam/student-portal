#!/usr/bin/env bash
# scripts/deploy_ansible.sh
# Packages Ansible roles and executes them on the EC2 app host via AWS SSM (Zero SSH ports required)
set -euo pipefail

REGION="${AWS_REGION:-ap-southeast-2}"
PROFILE="${AWS_PROFILE:-studentportalnew}"
PROJECT="student-portal"
ECR_REPO="149168123176.dkr.ecr.ap-southeast-2.amazonaws.com/student-portal-dev-app"

echo "=== [1/5] Finding active Student Portal EC2 instance ==="
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=${PROJECT}" "Name=instance-state-name,Values=running" \
  --region "${REGION}" --profile "${PROFILE}" \
  --query "sort_by(Reservations[].Instances[], &LaunchTime)[-1].InstanceId" --output text)

if [[ -z "${INSTANCE_ID}" || "${INSTANCE_ID}" == "None" ]]; then
  echo "Error: No running EC2 instance found for Project=${PROJECT}"
  exit 1
fi
echo "Target Instance: ${INSTANCE_ID}"

echo "=== [2/5] Packaging Ansible configuration bundle ==="
BUNDLE_B64=$(COPYFILE_DISABLE=1 tar --no-xattrs -czf - -C "$(dirname "$0")/../ansible" . | base64 | tr -d '\n')
echo "Bundle packaged (${#BUNDLE_B64} base64 bytes)"

echo "=== [3/5] Executing Ansible Playbook via AWS SSM Run Command ==="
REMOTE_SCRIPT="
set -euo pipefail
which ansible-playbook >/dev/null 2>&1 || dnf install -y ansible-core
mkdir -p /opt/student-portal/ansible
echo '${BUNDLE_B64}' | base64 -d | tar -xzf - -C /opt/student-portal/ansible
cd /opt/student-portal/ansible
ansible-playbook -i inventory/hosts.ini playbook.yml -e 'ecr_repo_url=${ECR_REPO}'
"

COMMAND_ID=$(aws ssm send-command \
  --instance-ids "${INSTANCE_ID}" \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[\"${REMOTE_SCRIPT//\"/\\\"}\"]" \
  --region "${REGION}" --profile "${PROFILE}" \
  --query "Command.CommandId" --output text)

echo "SSM Command dispatched: ${COMMAND_ID}. Waiting for completion..."

STATUS="Pending"
while [[ "${STATUS}" == "Pending" || "${STATUS}" == "InProgress" || "${STATUS}" == "Delayed" ]]; do
  sleep 4
  STATUS=$(aws ssm get-command-invocation \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --region "${REGION}" --profile "${PROFILE}" \
    --query "Status" --output text 2>/dev/null || echo "Pending")
  echo "SSM Status: ${STATUS}"
done

echo "=== [4/5] First Run Playbook Output ==="
aws ssm get-command-invocation \
  --command-id "${COMMAND_ID}" \
  --instance-id "${INSTANCE_ID}" \
  --region "${REGION}" --profile "${PROFILE}" \
  --query "StandardOutputContent" --output text

if [[ "${STATUS}" != "Success" ]]; then
  echo "Error: SSM Command failed with status ${STATUS}"
  aws ssm get-command-invocation \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --region "${REGION}" --profile "${PROFILE}" \
    --query "StandardErrorContent" --output text
  exit 1
fi

echo "=== [5/5] Idempotency Verification Run ==="
IDEMP_CMD_ID=$(aws ssm send-command \
  --instance-ids "${INSTANCE_ID}" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /opt/student-portal/ansible && ansible-playbook -i inventory/hosts.ini playbook.yml -e \"ecr_repo_url='${ECR_REPO}'\""]' \
  --region "${REGION}" --profile "${PROFILE}" \
  --query "Command.CommandId" --output text)

echo "Idempotency SSM Command dispatched: ${IDEMP_CMD_ID}. Waiting..."

STATUS="Pending"
while [[ "${STATUS}" == "Pending" || "${STATUS}" == "InProgress" || "${STATUS}" == "Delayed" ]]; do
  sleep 4
  STATUS=$(aws ssm get-command-invocation \
    --command-id "${IDEMP_CMD_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --region "${REGION}" --profile "${PROFILE}" \
    --query "Status" --output text 2>/dev/null || echo "Pending")
  echo "Idempotency Status: ${STATUS}"
done

aws ssm get-command-invocation \
  --command-id "${IDEMP_CMD_ID}" \
  --instance-id "${INSTANCE_ID}" \
  --region "${REGION}" --profile "${PROFILE}" \
  --query "StandardOutputContent" --output text

echo "=== Configuration & Deployment Succeeded via AWS SSM ==="
