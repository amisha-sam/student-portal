# Cost Analysis & Free-Plan Optimization Guide

## 1. Executive Summary
The Student Marks & Performance Portal is engineered with a **zero-waste, cost-aware architecture**. Deploying on AWS can quickly exhaust credits or free-tier limits if unoptimized components (such as NAT Gateways, Aurora clusters, or Secrets Manager) are used.

Our infrastructure is tailored specifically for the **AWS Free Tier** and credit sustainability in **`ap-southeast-2` (Sydney)**.

---

## 2. Resource Cost Matrix

| Resource Component | AWS Service | Sizing / Configuration | Hourly Cost | Monthly Cost (Continuous) | Free-Tier Allowance / Cost Optimization |
|---|---|---|---|---|---|
| **App Compute Host** | EC2 Graviton2 | `t4g.micro` (2 vCPU, 1 GB RAM, ARM64) | $0.0084 | $6.05 | Free Tier eligible (750 hrs/mo for Graviton2 t4g.micro) -> **$0.00** |
| **Relational Database** | Amazon RDS | `db.t4g.micro` (PostgreSQL 16, 20 GB gp3) | $0.0210 | $15.12 | Free Tier eligible (750 hrs/mo db.t4g.micro + 20 GB storage) -> **$0.00** |
| **Load Balancer** | Application Load Balancer (ALB) | 1 ALB, 2 AZs, HTTP only (Port 80) | $0.0225 | $16.20 | $0.0225/hr + $0.008/LCU-hr. Destroyed when idle -> **~$0.15/demo session** |
| **NAT Gateway** | VPC Networking | **OMITTED BY DESIGN** | $0.0450 | **$32.40 saved!** | Eliminated! App host runs in public subnet; RDS in private subnet. |
| **Container Registry** | Amazon ECR | 1 Private Repository (<500 MB) | $0.00 | $0.05 | 500 MB/mo free; lifecycle policy retains only 3 images. |
| **Terraform State Lock** | Amazon S3 + Native Lock | S3 Bucket + `use_lockfile = true` | $0.00 | $0.01 | **$0.00** (Eliminated DynamoDB table and read/write capacity units). |
| **Secret Storage** | SSM Parameter Store | 2 SecureStrings (`database_url`, `db_password`) | $0.00 | **$0.00** | Standard parameters are 100% free (saved $0.80/mo vs Secrets Manager). |
| **Host Configuration** | AWS Systems Manager | Run Command & Session Manager | $0.00 | **$0.00** | AWS core management features are completely free. |
| **Monitoring Stack** | Prometheus + Grafana | Docker containers on EC2 host | $0.00 | **$0.00** | Self-hosted on EC2 host with 2 GB swap; zero CloudWatch metrics cost. |
| **Total Estimated Cost** | — | — | **~$0.0519/hr** | **~$37.43/mo** | **~$0.00 with Free Tier & Destroy-After-Demo** |

---

## 3. Key Cost Optimization Strategies

### 1. Zero NAT Gateways (Saved ~$32.40/month)
A typical multi-tier AWS architecture places application instances in private subnets behind a NAT Gateway. NAT Gateways cost $0.045 per hour plus $0.045 per GB data processed, adding at least **$32.40/month** even with zero traffic.
- **Our Solution:** The EC2 app host resides in a public subnet with strict Security Group ingress rules (accepting HTTP traffic exclusively from the ALB). The RDS PostgreSQL database resides in isolated private subnets with **no internet access**, communicating only with the EC2 security group over port 5432.

### 2. S3 Native State Locking (No DynamoDB Table)
- Prior to Terraform 1.10, S3 backend required an AWS DynamoDB table for state locking.
- **Our Solution:** We leverage Terraform 1.10+ native S3 state locking via `use_lockfile = true`, eliminating DynamoDB tables, read/write units, and associated maintenance.

### 3. AWS SSM Parameter Store vs. Secrets Manager (Saved ~$0.80/month)
- AWS Secrets Manager charges $0.40 per secret per month plus $0.05 per 10,000 API calls.
- **Our Solution:** We use AWS Systems Manager Parameter Store `SecureString` (KMS-encrypted with AWS default key `alias/aws/ssm`), which is **free of charge** for standard parameters.

### 4. Graviton2 Architecture (`t4g.micro`)
- Graviton2 instances deliver up to 40% better price-performance than comparable x86_64 instances and qualify for free-tier usage.
- Furthermore, ARM64 matches the developer's macOS Apple Silicon M-series processor, allowing native Docker builds without emulation overhead.

### 5. Automated ECR Lifecycle Cleanup
- Docker images can quickly accumulate and incur storage charges.
- Our ECR module automatically expires untagged images older than 1 day and retains a maximum of 3 tagged images.

### 6. Demo-Driven Lifecycle (Near-Zero Spend)
By executing `terraform destroy` after evaluation sessions, running costs are limited strictly to the minutes when the jury demo is active, keeping total billings well below $1.00.
