# Operations Runbook — Student Marks & Performance Portal

## 1. Overview & Architecture
This runbook provides step-by-step procedures for deploying, maintaining, troubleshooting, and tearing down the Student Marks & Performance Portal on AWS.

```
Internet ---> ALB (Port 80) ---> EC2 Host (Port 8000: Flask WebApp)
                                         |
                                         +---> RDS PostgreSQL 16 (Port 5432: Private Subnet)
                                         +---> Node Exporter (Port 9100)
                                         +---> Prometheus (Port 9090)
                                         +---> Grafana (Port 3000)
```

---

## 2. Routine Deployment

### A. Deploy Infrastructure (Terraform)
1. Initialize Terraform with remote state locking:
   ```bash
   cd terraform/envs/dev
   terraform init
   ```
2. Review proposed changes:
   ```bash
   terraform plan -out=tfplan.binary
   ```
3. Apply changes (Checkpoint: verify costs before applying):
   ```bash
   terraform apply "tfplan.binary"
   ```

### B. Configure Host & Deploy Containers (Ansible via SSM)
1. Ensure latest Docker image is pushed to ECR:
   ```bash
   aws ecr get-login-password --region ap-southeast-2 --profile studentportalnew | \
     docker login --username AWS --password-stdin 149168123176.dkr.ecr.ap-southeast-2.amazonaws.com
   docker build --platform linux/arm64 -t 149168123176.dkr.ecr.ap-southeast-2.amazonaws.com/student-portal-dev-app:latest -f docker/Dockerfile .
   docker push 149168123176.dkr.ecr.ap-southeast-2.amazonaws.com/student-portal-dev-app:latest
   ```
2. Run Ansible over AWS Systems Manager:
   ```bash
   ./scripts/deploy_ansible.sh
   ```
3. Verify live endpoints:
   ```bash
   ALB_URL="http://$(terraform -chdir=terraform/envs/dev output -raw alb_dns_name)"
   curl -s "${ALB_URL}/health"
   curl -s "${ALB_URL}/metrics" | grep students_total
   ```

---

## 3. Rollback Procedure
If a bad Docker container image is pushed:
1. Identify the previous working git commit SHA or ECR image tag.
2. Tag previous image as `:latest`:
   ```bash
   aws ecr batch-get-image --repository-name student-portal-dev-app --image-ids imageTag=<PREVIOUS_SHA> --region ap-southeast-2 --profile studentportalnew --query 'images[].imageManifest' --output text > /tmp/manifest.json
   aws ecr put-image --repository-name student-portal-dev-app --image-tag latest --image-manifest file:///tmp/manifest.json --region ap-southeast-2 --profile studentportalnew
   ```
3. Re-run SSM deployment to restart the container:
   ```bash
   ./scripts/deploy_ansible.sh
   ```

---

## 4. Common Troubleshooting Scenarios

### Scenario A: Application Health Check Fails (502 Bad Gateway on ALB)
1. Connect to the EC2 host via Session Manager (no SSH required):
   ```bash
   INSTANCE_ID=$(aws ec2 describe-instances --filters "Name=tag:Project,Values=student-portal" "Name=instance-state-name,Values=running" --region ap-southeast-2 --profile studentportalnew --query "Reservations[0].Instances[0].InstanceId" --output text)
   aws ssm start-session --target "${INSTANCE_ID}" --region ap-southeast-2 --profile studentportalnew
   ```
2. Check running Docker containers and logs:
   ```bash
   docker ps -a
   docker logs --tail 100 student-portal-app
   ```
3. Verify database connectivity:
   ```bash
   docker exec -it student-portal-app python -c "from app import db; db.session.execute(db.text('SELECT 1')); print('DB OK')"
   ```

### Scenario B: Prometheus Alert `AppDown` Firing
1. Check Prometheus alert status:
   ```bash
   curl -s http://localhost:9090/api/v1/alerts
   ```
2. Verify app container state:
   ```bash
   docker inspect -f '{{.State.Status}}' student-portal-app
   ```
3. Restart container if stopped:
   ```bash
   docker restart student-portal-app
   ```

### Scenario C: Out-Of-Memory (OOM) Protection
- Instances run with 2GB swap space (`/swapfile`).
- Verify swap usage:
   ```bash
   free -h
   swapon --show
   ```

---

## 5. Teardown Procedure (Zero-Cost Operation)
To ensure no AWS credits are consumed when not in use:
```bash
cd terraform/envs/dev
terraform destroy -auto-approve
```
Verify all resources are cleaned:
```bash
aws ec2 describe-instances --filters "Name=tag:Project,Values=student-portal" "Name=instance-state-name,Values=running" --region ap-southeast-2 --profile studentportalnew --output table
```
