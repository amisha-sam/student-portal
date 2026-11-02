#!/usr/bin/env bash
# scripts/startup.sh
# One-command full deployment: Terraform IaC + Docker ECR + Ansible SSM
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== [1/4] Applying Terraform Infrastructure ==="
export TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache"
terraform -chdir="${ROOT_DIR}/terraform/envs/dev" apply -auto-approve

ECR_REPO=$(terraform -chdir="${ROOT_DIR}/terraform/envs/dev" output -raw ecr_repository_url)
ALB_DNS=$(terraform -chdir="${ROOT_DIR}/terraform/envs/dev" output -raw alb_dns_name)

echo "=== [2/4] Building & Pushing ARM64 Docker Image to ECR ==="
aws ecr get-login-password --region ap-southeast-2 --profile studentportalnew | \
  docker login --username AWS --password-stdin "${ECR_REPO}"
docker build --platform linux/arm64 -t "${ECR_REPO}:latest" -f "${ROOT_DIR}/docker/Dockerfile" "${ROOT_DIR}"
docker push "${ECR_REPO}:latest"

echo "=== [3/4] Configuring Host & Running Containers via Ansible SSM ==="
"${ROOT_DIR}/scripts/deploy_ansible.sh"

echo "=== [4/4] Verifying Live Health Endpoint ==="
curl --fail --retry 5 --retry-delay 3 "http://${ALB_DNS}/health"

echo ""
echo "=========================================================="
echo " Student Portal is LIVE on AWS!"
echo " Portal URL: http://${ALB_DNS}"
echo "=========================================================="
