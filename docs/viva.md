# Comprehensive Viva Q&A Guide & Jury Defense

> **Project Title:** Student Marks & Performance Portal on AWS (DevOps Capstone)  
> **Student Owner:** Amisha Sam  
> **Target Account ID:** `149168123176` | **Region:** `ap-southeast-2` (Sydney)  
> **Repository:** `github.com/amisha-sam/student-portal`

---

## 1. Project Goal & Business Value

### Q1: What is the problem statement, and what does this project deliver?
- **Problem:** In schools and colleges, teachers manually compute marks, calculate percentages, and assign letter grades. Because this process is manual, spotting students who fall behind or require urgent academic intervention is slow, inconsistent, and often too late.
- **Solution:** A modern web portal that automates marks recording, calculates weighted averages and grades, provides instant PDF report cards and CSV summaries, and features an automated **"Needs Support" (At-Risk)** early detection engine.
- **DevOps Goal:** The project demonstrates a production-grade AWS DevOps lifecycle: Infrastructure as Code (Terraform), Zero-SSH configuration management (Ansible via AWS SSM), automated CI/CD with security scanning (GitHub Actions + Trivy), full-stack containerization (Docker on ARM64 Graviton2), multi-tier observability (Prometheus + Grafana with Academic dashboards), and cost engineering.

---

## 2. Phase A: Application & Containers

### Q2: What application stack was chosen, and why?
- **Tech Stack:** Python 3.12, Flask, Flask-SQLAlchemy (pinned to `2.0.36`), PostgreSQL 16 with `psycopg2-binary`, Bootstrap 5.3, Chart.js, ReportLab (PDF), and `prometheus_client`.
- **Reasoning:** Flask is lightweight, consumes under 100 MB of RAM, and starts up in milliseconds. It provides clean separation of concerns and runs effortlessly on small cloud instances (`t4g.micro`).
- **Alternative:** Django was considered, but its heavy ORM, admin site, and high memory footprint make it excessive for micro-instances. FastAPI is async-centric and adds needless overhead for server-rendered Jinja templates.

### Q3: Why Gunicorn with `--workers 1 --threads 4`?
- **Reasoning:** Prometheus metrics are kept in application memory. In multi-worker Gunicorn configurations, each HTTP request hits a different worker alternately, causing metrics counters to jump backward and scrape results to fluctuate erratically. Running 1 master worker with 4 concurrent threads ensures high concurrency while keeping Prometheus counters and gauges completely consistent.

### Q4: How is the "At-Risk" calculation performed?
- **Rule:** A student is flagged as needing academic support if:
  1. Any individual subject score average is `< AT_RISK_SUBJECT` (default 40%), OR
  2. The overall academic average across all subjects is `< AT_RISK_OVERALL` (default 50%).
- **Key Feature:** The portal records and displays the exact *reasons* for each intervention (e.g. *"Maths: 29% (below 40%); Overall: 35% (below 50%)"*), which are embedded in both the web UI and the official PDF report card.

---

## 3. Phase B: Infrastructure as Code (Terraform)

### Q5: Why Terraform instead of AWS CloudFormation?
- **Reasoning:** Terraform is cloud-agnostic, features superior state inspection (`terraform plan`, `terraform state`), supports modular reusability with clean input/output contracts, and has an active ecosystem.
- **Terraform 1.10 Native State Locking:** We use native S3 bucket locking (`use_lockfile = true`) directly supported in Terraform 1.10+, eliminating the legacy requirement of maintaining an Amazon DynamoDB table and saving costs.

### Q6: Walk us through the network topology and security architecture.
- **VPC Design:** A custom VPC (`10.0.0.0/16`) spanning 2 Availability Zones (`ap-southeast-2a` and `ap-southeast-2b`).
- **Subnet Separation:** 2 public subnets for the Application Load Balancer and EC2 host; 2 private subnets for the RDS PostgreSQL database subnet group.
- **Cost Engineering (Zero NAT Gateway):** We deliberately omitted NAT Gateways to save ~$32.40/month. The app host lives in the public subnet with an elastic IP/public IP, while RDS lives in the private subnet with **zero internet route**.
- **Defense-in-Depth Security Groups:**
  1. ALB SG: Accepts HTTP (port 80) from `0.0.0.0/0`.
  2. App SG: Accepts traffic on port 8000 **strictly from the ALB security group**. No SSH port 22 is open anywhere.
  3. RDS SG: Accepts PostgreSQL traffic on port 5432 **strictly from the App security group**.

### Q7: Why AWS Graviton2 (`t4g.micro`)?
- **Reasoning:** Graviton2 (64-bit ARM Neoverse cores) provides up to 40% better price-performance compared to x86_64 instances and is eligible for the AWS 750-hour free tier. Moreover, because the developer machine is an Apple Silicon Mac (`darwin_arm64`), Docker images built locally compile natively for ARM64 without architecture mismatch (`exec format error`).

---

## 4. Phase C: Configuration Management (Ansible + AWS SSM)

### Q8: Why use Ansible via AWS SSM rather than SSH?
- **Security:** Opening port 22 to the public internet exposes servers to brute-force attacks and requires managing, rotating, and securing SSH private keys (`.pem`).
- **AWS Systems Manager (SSM):** SSM uses an outbound HTTPS agent connection (TLS 443) back to AWS. No inbound ports need to be opened. IAM role permissions control who can execute commands.
- **Ansible Execution:** The Ansible playbook bundle is packaged and executed locally on the host via SSM Run Command (`AWS-RunShellScript`), ensuring full idempotency and complete audit trails in AWS CloudTrail and SSM Command History.

### Q9: How is idempotency ensured?
- Every Ansible role task uses state verification:
  - Swap: Only formats and enables if `/swapfile` does not exist.
  - Docker network: Only creates `student-portal-net` if it doesn't already exist.
  - Containers: Checks `docker inspect -f '{{.State.Running}}'` and pulls images before recreating.
  - App DB: `flask seed` checks `if not User.query.filter_by...` before inserting.
  - A second consecutive run of the playbook yields `changed=0` on all stable resources.

---

## 5. Phase D: CI/CD Pipeline (GitHub Actions)

### Q10: Describe your continuous integration and deployment pipeline.
- **Pipeline 1 (`app-ci.yml`):**
  1. **Lint & Test:** Runs `flake8` for PEP 8 compliance and `pytest` for 11 unit tests with test coverage reporting.
  2. **Container Security:** Runs `hadolint` on the Dockerfile, sets up QEMU & Docker Buildx for ARM64, and runs **Aqua Security Trivy** vulnerability scanning for HIGH/CRITICAL CVEs.
  3. **Continuous Deployment (on push to `main`):** Builds and pushes the versioned image to Amazon ECR, dispatches an SSM Run Command to the EC2 host to pull `:latest` and restart the container, and runs an end-to-end smoke test against the live ALB `/health` URL.
- **Pipeline 2 (`infra.yml`):**
  - Runs `terraform fmt -check`, `tflint`, and `terraform validate` on pull requests to ensure infrastructure code hygiene.

### Q11: Why are AWS credentials stored as GitHub Secrets instead of IAM OIDC?
- **Root Cause & Discovery:** During the pre-flight infrastructure phase, probing the AWS account revealed that the parent organization has a Service Control Policy (SCP: `p-nzqi9r7t`) that explicitly denies `iam:*OpenIDConnectProvider*`.
- **Engineering Solution:** Rather than being blocked, we documented this constraint, disabled OIDC in Terraform (`enable_github_oidc = false`), and configured least-privilege IAM credentials as encrypted GitHub Repository Secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `ECR_REPOSITORY_URL`, `ALB_DNS_NAME`).

---

## 6. Phase E: Monitoring & Observability

### Q12: What metrics stack is deployed, and what are the three Grafana dashboards?
- **Stack:** Prometheus v2.54, Prometheus Node Exporter v1.8, and Grafana OSS v11.1 deployed in Docker containers and connected via `student-portal-net`.
- **Three Provisioned Dashboards:**
  1. **Academic Performance (Business KPI):** Real-time gauge of students at risk per class, class average percentages, and total marks entries submitted.
  2. **Application Metrics:** Request rates (`http_requests_total`), p95 request latency, error distribution (4xx/5xx), and database connection health.
  3. **Infrastructure Metrics:** Host CPU utilization, memory and 2GB swap usage, disk I/O, and network throughput via Node Exporter.
- **Dashboard as Code:** All datasources and dashboards are provisioned declaratively from JSON and YAML definitions upon container boot—zero manual clicking in the Grafana UI.

### Q13: How were alerts tested?
- **Alert Rule:** `AppDown` triggers if `up{job="student_portal_app"} == 0` for > 30 seconds.
- **Drill:** We stopped the `student-portal-app` container (`docker stop student-portal-app`). After 35 seconds, Prometheus transitioned the alert to `firing`. Restarting the container (`docker start student-portal-app`) cleared the alert within 15 seconds.

---

## 7. Phase F: Security, Secrets & Reliability

### Q14: How are secrets managed without hardcoding?
- Database passwords and the full database URL are generated dynamically by Terraform (`random_password`) and stored in **AWS Systems Manager Parameter Store as `SecureString`** (encrypted with AWS KMS).
- The EC2 instance profile has an IAM policy restricted to `ssm:GetParameter` on `/student-portal/dev/*`.
- The application container reads parameters at startup via `/opt/student-portal/app.env` with `0600` permissions. No plaintext secrets exist in Git.

### Q15: How does the application self-heal if an instance fails?
- The EC2 host is governed by an **Auto Scaling Group (ASG)** with `min=1, max=1, desired=1`.
- If an instance experiences hardware degradation or fails ELB health checks, the ASG automatically terminates the unhealthy instance and launches a replacement from the Launch Template.

---

## 8. 10-Minute Live Jury Demonstration Script

1. **Step 1: Architecture Walkthrough (1 min):** Show VPC, ALB, EC2 Graviton host, private RDS, and SSM management.
2. **Step 2: Live Application Demo (2 mins):**
   - Open ALB DNS: `http://student-portal-dev-alb-2065164625.ap-southeast-2.elb.amazonaws.com`
   - Log in as `teacher` / `teacher123`.
   - Show Dashboard with KPI cards and Chart.js grade distribution.
   - Navigate to **"Needs Support"** page and explain early intervention criteria.
   - Download Student Report Card PDF (`/report/1.pdf`) showing formatted academic record.
   - Download CSV Class Summary (`/export.csv`).
3. **Step 3: Terraform & IaC Evidence (2 mins):**
   - Show `terraform/envs/dev/main.tf` modular structure.
   - Run `terraform -chdir=terraform/envs/dev output` showing S3 native locked state.
4. **Step 4: Zero-SSH Configuration (Ansible + SSM) (1 min):**
   - Show `./scripts/deploy_ansible.sh` executing over AWS SSM.
   - Show that port 22 is completely closed in security groups.
5. **Step 5: Observability & Alerting Drill (2 mins):**
   - Open Prometheus targets showing `student_portal_app`, `node_exporter`, and `prometheus` all `UP`.
   - Open Grafana: show **Academic Performance** dashboard with live metrics.
   - Execute alert drill: stop app container, observe `AppDown` alert fire, restart container and show auto-resolution.
6. **Step 6: CI/CD Pipeline & GitHub Actions (1 min):**
   - Show GitHub Actions workflows passing (`app-ci.yml` and `infra.yml`) with flake8, pytest, and Trivy security scans.
7. **Step 7: Cost Awareness & Teardown (1 min):**
   - Show `docs/cost.md` demonstrating $0.00/month free-tier architecture and runbook for `terraform destroy`.
