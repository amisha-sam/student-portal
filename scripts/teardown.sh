#!/usr/bin/env bash
# scripts/teardown.sh
# Safely tears down all AWS resources in dev environment to conserve credits
set -euo pipefail

echo "=========================================================="
echo " Starting Student Portal AWS Infrastructure Teardown"
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

export TF_PLUGIN_CACHE_DIR="$HOME/.terraform.d/plugin-cache"

echo "Destroying dev environment resources..."
terraform -chdir="${ROOT_DIR}/terraform/envs/dev" destroy -auto-approve

echo "Teardown complete. All cost-generating resources removed."
