# PROJECT CONTEXT: Student Marks & Performance Portal (AWS DevOps Capstone)

> Read this whole file before doing anything. It is the single source of truth for the project.
> The owner is a student on a macOS (Apple Silicon) laptop with a **free-plan AWS account**. A jury will grade the result.

---

## 1. Goal

Build, deploy and operate a **Student Marks and Performance Portal** on AWS, using a full DevOps toolchain.
The jury grades the **DevOps practice** (IaC, CI/CD, config management, monitoring, security, cost awareness, documentation) as much as the app itself. A working demo plus clean evidence of each practice is the aim.

**Problem statement:** Teachers calculate marks, totals and grades manually, which makes it hard to spot students who need extra support.

**Solution:** A portal that records subject marks, calculates grades automatically, and flags students who fall below a defined score.

**Basic features (must work):** marks entry, grade calculation, student reports.
**Headline feature (make it prominent):** at-risk detection ("Needs Support" page).

## 1a. Ownership: the agent does everything, end to end

The owner is delegating the **entire project**. The agent is responsible for every layer and must do the work itself instead of handing instructions back:

- **CLI / local machine:** run every command itself in the terminal (Git, GitHub CLI, Docker, Terraform, AWS CLI, Ansible, tests). Install missing tools (for example with Homebrew) after telling the owner what will be installed. Do not reply with "run this command yourself" unless it truly needs the owner (root console login, MFA, billing, browser OAuth, approvals).
- **Frontend:** design and build a polished, responsive UI. Clean layout, consistent styling, clear at-risk highlighting, charts on the dashboard (grade distribution, subject averages, at-risk per class), form validation and friendly error messages, accessible colours, and a good mobile view. It should look like a finished product when shown to a jury, not a bare prototype.
- **Backend:** application logic, database models and migrations, authentication and role checks, input validation, REST endpoints (including a small JSON API for the dashboard charts), PDF and CSV reports, logging, error handling, health and metrics endpoints, configuration through environment variables, and a solid automated test suite.
- **AWS / cloud:** all infrastructure through Terraform (never by clicking in the console), including networking, compute, database, registry, IAM, parameters/secrets, load balancer, monitoring host, OIDC for CI, budgets and alarms where permitted. Then deploy the app, run Ansible, run the pipelines, and verify everything works live.
- **DevOps and monitoring:** GitHub Actions workflows, Ansible roles, Prometheus rules, and Grafana dashboards, provisioned as code.
- **Quality and documentation:** tests, linting, security scans, README, architecture diagram, runbook, cost table, viva Q&A, screenshots.
- **Verification:** after each phase, prove it works yourself (run the tests, curl the endpoints, open the page, check the AWS resources, read the logs) and report evidence. Fix problems you find, and do not hand the owner a broken step.

**Autonomy and safety, reconciled:** the agent drives all the work and runs commands without being asked to for read-only, local, and `plan` operations. It stops only at **checkpoints** (section 9, rule 1): the first `terraform apply`, any `destroy`, anything that creates cost beyond the plan the owner approved, IAM changes outside the project, pushes to `main`, and the owner-only actions in section 12. At a checkpoint, give a short summary (what, why, estimated cost) and wait for a yes.

## 2. Mandatory tech stack (replacements allowed where noted)

| Required item | Choice for this project |
|---|---|
| Terraform / CloudFormation | **Terraform** (>= 1.10, S3 native state locking, no DynamoDB) |
| Jenkins / GitHub Actions | **GitHub Actions** |
| Ansible / AWS SSM | **Both**: Ansible for configuration, SSM for access, deploy commands and patching |
| Grafana + Prometheus | **Both**, plus node_exporter |

Do not swap these out without asking the owner. CloudFormation is not used for this project.

## 3. Hard constraints (read carefully)

1. **AWS free plan, credit based.** Remaining credits were about $118 and the plan expires about **29 April 2027**. Running resources consume credits. Every design choice must be cost-aware.
2. **Region: `ap-southeast-2` (Sydney).** Make region a Terraform variable. In `ap-south-1` (Mumbai) the account's organisation **Service Control Policy explicitly denied** EC2 actions. Do not use Mumbai.
3. **IAM user:** `studentportaladmin` with `PowerUserAccess`. This does **not** include IAM. Creating IAM roles will fail until the owner attaches `IAMFullAccess` (via the root user, in the console). Check this in pre-flight (section 4) and tell the owner if it is still missing. Never ask for root credentials.
4. **Free-plan limits:** only certain small instance types are allowed, Aurora and large RDS classes are not, and some services are restricted. Check eligibility with the commands in section 4. Do not assume.
5. **No NAT Gateway** (hourly cost). App instances live in public subnets with tight security groups. RDS lives in private subnets and needs no internet access.
6. **CPU architecture trap:** the owner's Mac is **arm64**, while a `t3.*` EC2 instance is **x86_64**. Docker images built on the Mac will fail on EC2 with `exec format error`. Build images in GitHub Actions (amd64 runners) with `docker buildx --platform linux/amd64`, or use a Graviton type (`t4g.*`) if it is free-plan eligible. State which you chose and why.
7. **Existing unrelated resource:** a CloudFormation stack named `fsdemo` (API Gateway, Lambda, DynamoDB) exists in the account. It is **not part of this project. Do not modify or delete it.**
8. **Secrets:** never commit credentials, keys, `.tfvars` with secrets, or state files. GitHub Actions authenticates to AWS with **OIDC**, not stored access keys.
9. **Budget:** the owner must have an AWS Budget alert (about $2 to $5). Verify, and remind them if missing.

## 4. Pre-flight checks (do these first, read-only)

```bash
aws sts get-caller-identity                 # must show user/studentportaladmin
aws configure get region                    # must be ap-southeast-2
terraform -version                          # >= 1.10
docker --version && docker compose version
gh auth status
aws ec2 describe-instance-types --region ap-southeast-2 \
  --filters Name=free-tier-eligible,Values=true \
  --query "InstanceTypes[*].InstanceType" --output text
# IAM permission test (creates and deletes a throwaway role):
aws iam create-role --role-name tmp-probe --assume-role-policy-document \
 '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
 && aws iam delete-role --role-name tmp-probe
```

Also probe (read-only) that S3, RDS, ELBv2, Autoscaling, ECR, SSM and Secrets Manager respond without an explicit-deny SCP error. **Distinguish the two kinds of AccessDenied:**
- "no identity-based policy allows ..." -> the owner's IAM permissions are missing; fixable by the owner.
- "explicit deny in a service control policy" -> the organisation blocks it; **cannot be fixed**, so redesign around it or tell the owner to ask their instructor/admin.

Report the results and adapt the plan before writing infrastructure.

## 5. Target architecture

```
Developer -> GitHub -> GitHub Actions (lint, test, scan, build amd64 image, terraform plan/apply, deploy)
                          |
                          v                       Terraform provisions everything below
                    ECR (image)
Internet -> ALB (toggle) -> EC2 app host (Docker: Flask + gunicorn)
                                  |
                                  v
                       RDS PostgreSQL 16 (private subnets, encrypted, single-AZ)

Monitoring: Prometheus + Grafana (+ node_exporter) in Docker, scraping /metrics and the host
Config:     Ansible roles (docker, node_exporter, app, prometheus, grafana) run via SSM
Access:     SSM Session Manager only. No SSH port open.
State:      S3 bucket (versioned, encrypted, locked with use_lockfile)
Secrets:    SSM Parameter Store SecureString (free). Secrets Manager only if credits allow ($0.40/secret/month).
Alarms:     Prometheus alert rules (plus optional CloudWatch alarm as backup)
```

Design notes:
- ALB is behind a Terraform variable `enable_alb` (default true for demos, false while idle). If the ALB is unavailable on the plan, fall back to one EC2 instance with an Elastic IP and document the trade-off.
- Auto Scaling Group with min=max=1 (self-healing) is preferred over a bare instance, if the plan allows it.
- App + Prometheus + Grafana on a 1 GB instance is tight. Prefer a larger eligible type for the monitoring host, a separate small instance, or add swap and say so in the docs.
- RDS subnet groups need subnets in at least two AZs even for a single-AZ database.
- Tag every resource: `Project=student-portal`, `ManagedBy=terraform`, `Environment=<dev|prod>`.

## 6. Application specification (build from scratch if needed)

**Stack:** Python 3.12, Flask, Flask-SQLAlchemy, Flask-Login, PostgreSQL, Bootstrap with Jinja templates plus a light charting library (for example Chart.js), gunicorn, reportlab, prometheus_client. Keep the code readable. Use Alembic or Flask-Migrate for schema migrations. The **frontend must look professional and be responsive** (see section 1a), and the backend must have proper validation, error pages (403/404/500), logging and tests. The sections below are the minimum feature set. Improving the design and usability beyond it is encouraged as long as it stays simple to explain.

**Roles:** `admin`, `teacher` (full access), `student` (sees only their own report; username = roll number).

**Data model:** `User(username, password_hash, role)`, `Student(roll, name, class_name)`, `Subject(name)`, `Mark(student, subject, exam, score 0-100)` with a unique constraint on (student, subject, exam).

**Grading** (overall % = average of per-subject averages): `>=90 A+`, `>=80 A`, `>=70 B`, `>=60 C`, `>=50 D`, else `F`.

**At-risk rule (configurable by env vars):** a student is flagged if **any subject average < `AT_RISK_SUBJECT` (default 40)** or **overall < `AT_RISK_OVERALL` (default 50)**. Always store and show the *reasons*.

**Pages and endpoints:**
- `/login`, `/logout`
- `/` dashboard (class filter, totals, average, at-risk count, at-risk rows highlighted red)
- `/marks` marks entry: choose class, subject, exam; enter marks per student; validate 0 to 100; upsert
- `/at-risk` "Needs Support" list with reasons
- `/report/<id>` HTML report and `/report/<id>.pdf` PDF report card
- `/export.csv` class summary
- `/health` (checks DB), `/metrics` (Prometheus)
- Seed command: `flask --app app seed` creates demo users, subjects and students. **Demo passwords are for local use only. In AWS, passwords come from environment or Parameter Store, never hard-coded.**

**Prometheus metrics (names matter for the dashboards):**
`http_requests_total{method,endpoint,status}`, `http_request_duration_seconds{endpoint}`, `marks_entries_total`, `students_total`, `students_at_risk{class_name}`, `class_average{class_name}`.

**Known pitfalls (already hit once, do not repeat):**
- Pin `SQLAlchemy==2.0.36` and use the URL scheme `postgresql+psycopg2://` with `psycopg2-binary`. Unpinned SQLAlchemy tried to load `psycopg` (v3) and crashed.
- Run gunicorn with **one worker plus threads** so Prometheus counters stay consistent.
- A corrupted Docker image pull once caused `exec format error` locally; `docker compose pull` fixed it.
- Include unit tests for grading boundaries and at-risk logic, and keep them in CI.

## 7. Repository layout

```
student-portal/
├── app/                  # Flask app, templates, tests, requirements
├── docker/               # Dockerfile, docker-compose.yml
├── terraform/
│   ├── bootstrap/        # one-time S3 state bucket (local state)
│   ├── modules/          # vpc, security, ecr, rds, compute, alb, iam, monitoring
│   └── envs/dev/         # backend.tf, main.tf, variables.tf, outputs.tf, example.tfvars
├── ansible/              # inventory, playbook.yml, roles/{docker,node_exporter,app,prometheus,grafana}
├── monitoring/           # prometheus.yml, alert_rules.yml, grafana provisioning + dashboard JSON
├── .github/workflows/    # app-ci.yml, infra.yml
├── docs/                 # architecture diagram, runbook, cost table, viva Q&A, screenshots
├── AGENTS.md             # this file
└── README.md
```

Use branches and pull requests (`feature/...`), small meaningful commits, and Conventional-Commit style messages. `main` stays deployable.

## 8. Phases and acceptance criteria

Complete in order. **A phase is done only when its checks pass and you have shown the owner the evidence.**

**Phase A: Application and containers**
- Works locally with `docker compose up --build` and the seed command.
- Done when: unit tests pass; login works for all three roles; marks entry validates; at-risk page shows reasons; PDF and CSV download; `/health` returns ok; `/metrics` lists the custom metrics.

**Phase B: Terraform infrastructure**
1. `bootstrap/`: versioned, encrypted, public-access-blocked S3 state bucket (`<project>-tfstate-<account-id>`).
2. `envs/dev` backend: `use_lockfile = true`.
3. Modules, applied **one at a time**: VPC (2 public and 2 private subnets, IGW, no NAT) -> security groups -> ECR (with lifecycle policy keeping the last few images) -> IAM (EC2 role with SSM, ECR pull and Parameter Store read) -> RDS -> compute (launch template, ASG, user data minimal) -> ALB (toggle) -> outputs.
- Done when: `terraform fmt -check`, `validate` and `plan` are clean; `apply` succeeds; the app is reachable (ALB DNS or Elastic IP); the app talks to RDS; the instance is reachable through Session Manager; `terraform destroy` removes everything cleanly (test this once).

**Phase C: Configuration management (Ansible plus SSM)**
- Roles: `docker`, `node_exporter`, `app`, `prometheus`, `grafana`. Playbook must be **idempotent** (second run shows `changed=0`).
- Run through SSM (for example Ansible local mode triggered by an SSM Run Command or State Manager association, or the `aws_ssm` connection plugin with its S3 transfer bucket). Enable Patch Manager baseline for OS patching.
- Done when: a fresh instance can be fully configured by one command, and no SSH port is open.

**Phase D: CI/CD (GitHub Actions)**
- `app-ci.yml`: on push/PR -> lint (ruff or flake8) -> pytest -> hadolint -> build amd64 image -> **Trivy scan** (fail on HIGH/CRITICAL where feasible) -> push to ECR (main only) -> deploy via SSM Run Command (pull, restart) -> smoke test `/health`.
- `infra.yml`: on PR -> `fmt`, `validate`, `tflint`, `checkov` or `tfsec`, `plan` posted as a PR comment. On merge -> `apply` behind a **GitHub Environment with manual approval**.
- AWS auth through **GitHub OIDC** and a least-privilege IAM role (created by Terraform). No access keys in GitHub secrets.
- Done when: a code change pushed to a branch passes CI, and merging deploys it with evidence in the Actions tab.

**Phase E: Monitoring**
- Prometheus scrapes the app `/metrics`, node_exporter and itself. Grafana datasource and dashboards are **provisioned from files** (no manual clicking).
- Three dashboards: (1) Infrastructure (CPU, memory, disk), (2) Application (request rate, p95 latency, error rate), (3) **Academic performance** (at-risk students per class, class average, marks entered). The third one is the standout.
- Alert rules: app down, high 5xx rate, CPU > 80%, at-risk percentage above threshold. Deliver to email or Slack if feasible, otherwise show them firing in the Prometheus/Grafana UI.
- Done when: stopping the app container triggers the "app down" alert and restarting it clears the alert.

**Phase F: Security and polish**
- Encrypted RDS and S3; private DB; least-privilege IAM; no hard-coded secrets; input validation; security headers; HTTPS via ACM if the owner has a domain (otherwise document why HTTP is used for the demo).
- Optional extras: load test (k6 or `hey`) to show scaling or latency, automated RDS backup and restore demo, CloudWatch alarm.

**Phase G: Documentation and demo**
- `README.md`: overview, architecture diagram, prerequisites, setup, deploy, teardown, screenshots.
- `docs/runbook.md` (deploy, rollback, common failures), `docs/cost.md` (table of resources, rough monthly cost, how the free plan and destroy-after-demo keep it near zero), `docs/viva.md` (likely jury questions with short answers, including why each tool and design choice was made).
- A 10-minute demo script (section 10).

## 9. Rules for the agent (how to work)

1. **Checkpoints: ask before anything that costs money or is destructive.** `terraform apply`, `terraform destroy`, creating or deleting AWS resources, changing IAM, or pushing to `main` need the owner's explicit go-ahead. Everything else (coding, local Docker, tests, linting, read-only AWS commands, `terraform plan`, Git commits on feature branches) you run yourself without asking. Once the owner approves a plan, execute it fully and verify it, and do not ask again for each small step inside that approved plan.
2. **Always show `terraform plan` output and summarise it** (resources added, changed, destroyed, and the estimated hourly cost) before asking to apply.
3. **Work in small steps.** Build, verify, show evidence, then move on. Do not generate the whole repo in one pass.
4. **Never print, log or commit secrets.** Do not paste credentials in chat. Use environment variables, Parameter Store and OIDC. Keep `.gitignore` covering `*.tfstate*`, `.terraform/`, `*.tfvars` (except `example.tfvars`), `.env`, `.venv/`.
5. **Explain as you go.** The owner is a student who must explain every part to a jury. After each phase, add 3 to 6 plain-language lines to `docs/viva.md` covering what it does, why this tool, and what the alternative was.
6. **Reduce cost by default.** Smallest eligible sizes, single-AZ, no NAT, short log retention, ECR lifecycle policy, and an `enable_alb` style toggle. Remind the owner to run `terraform destroy` after each working session. Provide `scripts/teardown.sh` and `scripts/startup.sh` notes.
7. **Verify, do not assume.** Free-plan rules, instance eligibility, Terraform provider arguments and action versions change. Check the current documentation or run the CLI instead of relying on memory. Pin versions (providers, GitHub Actions, Docker base images, Python packages).
8. **Stay in scope.** Do not touch the `fsdemo` stack or any resource not tagged `Project=student-portal`.
9. **When blocked by permissions, diagnose first.** Say which kind of AccessDenied it is (section 4) and what exact action the owner must take.
10. Keep code simple, commented where non-obvious, and runnable by a beginner.

## 10. Jury checklist and demo script

| Expectation | Evidence to show |
|---|---|
| Solves the problem | At-risk detection, auto grades, reports |
| Infrastructure as Code | Modular Terraform, remote state, plan output |
| CI/CD | Two pipelines with tests, scan and approval |
| Configuration management | Ansible roles (idempotent), SSM Run Command |
| Monitoring | Prometheus, 3 Grafana dashboards, alert firing and recovery |
| Security | OIDC, Session Manager, private DB, encryption, no secrets in repo |
| Reliability | ASG self-healing, RDS backups |
| Cost awareness | Budget alert, cost table, destroy-after-demo |
| Documentation | README, diagram, runbook, viva Q&A |

**10-minute demo:** (1) architecture diagram; (2) teacher logs in, enters marks, at-risk students appear; (3) download a report card PDF; (4) push a small code change, show the Actions run and the live update; (5) Grafana: infrastructure and academic dashboards; (6) stop the app to trigger the alert, then recover; (7) show `terraform plan` and explain `destroy`.

## 11. Definition of done for the whole project

- Fresh clone plus documented steps reproduces the environment.
- `terraform apply` builds it, the pipeline deploys it, and `terraform destroy` removes it.
- Every row in the jury checklist has screenshots or logs in `docs/`.
- No secrets in Git history. README is complete.
- The owner can explain every component without notes.

## 12. Owner actions the agent cannot do (remind them)

- Attach `IAMFullAccess` to `studentportaladmin` while signed in as root (then stop using root), and enable MFA on root.
- Create the AWS Budget alert.
- Approve production applies and GitHub Environment deployments.
- Decide whether the GitHub repo is public or private (`github.com/amisha-sam/student-portal`).

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance for the new AWS experience

This user has signed up for the new AWS experience. This experience lets you sign into AWS using a social provider and requires the following additional context.

Where this guidance conflicts with the project's own instructions, the project's instructions take precedence.

## Context

### Terminology:

- Say "project" instead of "account" — a project contains an AWS account and settings for sharing with other collaborators
- Say "team member" instead of "IAM user" — users are invited by email, not created or federated in IAM
- Say "AWS Settings" when referring to management tasks at [settings.aws.com](https://settings.aws.com/) (project management, billing, team members, spend limits). Users view their actual AWS resources in the AWS Management Console.
- Say "selected Region" when referring to the user's Region — not "home Region"
- The user has a managed IAM experience. This includes a managed service control policies (SCP) and resource control policies (RCP) that govern the use of AWS. They will still need to use IAM to create policies to let services work with each other. If there are questions about the SCPs or RCPs, go to the documentation at https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html

### Constraints:

- All projects share a single AWS Region determined by the user's contact address. Resources cannot be created in other Regions
- When developing:
  - MUST create all Regional resources in the project's assigned Region
  - You CAN create AWS WAF and Cloudwatch Logs resources in us-east-1 when there are global resources (like a global WAF instance) that require a connection to dependencies in us-east-1. You should not use these for any other reason, because resources in the selected Region will provide lower cost (due to no cross-Region traffic), increased availability (due to no cross-Region traffic), and easier manageability (due to not needing to look in another Region). When you need to do an inventory of resources, you need to look in both the selected Region and us-east-1 for Cloudwatch Logs or WAF resources.
  - MUST NOT attempt to create Lambda, API Gateway, or other Regional resources in any other Region
  - MUST direct users to confirm their Region in AWS Settings > View all projects > Overview > Additional Info > Region. If the user cannot confirm their Region, check in ~/.aws/config
  - MUST NOT use Lambda@Edge — excluded from both Lambda and CloudFront
  - MUST NOT use CloudFormation StackSets — no multi-account or multi-Region deployments
  - MUST NOT attempt cross-Region actions — no cross-Region replication for DynamoDB/S3/RDS, no multi-Region KMS keys
  - MUST NOT use Route 53 cross-Region routing — geolocation, latency-based, and failover routing policies are not available
  - CloudFront is a global service and its actions ARE allowed in `us-east-1`. A user can create a CloudFront distribution pointing to their project-region Lambda function URL or API Gateway. However, Lambda and API Gateway themselves MUST NOT be created in `us-east-1` — they must be in the project Region.
  - Reduced availability in `eu-north-1` specifically: Amazon Rekognition, Amazon Textract, Amazon Personalize, AWS App Runner are not available in that Region.
- IAM permissions for human access are managed by AWS. Don't assign roles to team members unless absolutely necessary
- The user may have a spend limit if they are on the paid plan. The limit that pauses their project if it's exceeded. If resources suddenly become inaccessible, ask if they have a spend limit configured. Only project owners can modify a spend limit.
- When developing:
  - MUST ask about spend limit status if the user reports sudden "Access Denied" errors on operations that previously worked
  - MUST direct users to check spend status in AWS Settings > Billing
  - MUST check if a user has upgraded their account to the paid plan
  - MUST ask the user if they want to clean up the successfully created resources or keep them to reduce cost
- The user sets up billing, creates spend limits, and retrieves and pays invoices in AWS Settings. The user creates budgets and optimizes their costs in the AWS Billing and Cost Management console
- Not all AWS services are available. If a service isn't working, do the following:
  1. Run the command `aws freetier get-account-plan-state`
  2. If accountPlanType": "FREE", check the [Free Tier supported services list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#supported-services-free-tier) next,
  3. If accountPlanType": "PAID", check the [Paid Tier supported services list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#supported-services-paid-plan).
  4. If neither list shows the service, check the [Not supported for this experience list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html#unsupported-services). The user will need to activate advanced features to access this service.
- Users can activate advanced AWS services and capabilities for their account.
- For any AWS task or question — building, configuring, migrating, debugging, or operating a service, writing SDK code, authoring CDK/CloudFormation, or answering how a service works — first call `aws___search_documentation` with topic `agent_skills` and load the matching skill with `aws___retrieve_skill`. Do this even when you believe you know the answer: skills carry current service behavior that your training may not. Prefer the skill's guidance over general knowledge. Skip it only for work that does not involve AWS.

### Help level

- help_level: HIGH. Explaining what each step does and why before executing it, suggesting alternatives, flagging best practices and trade-offs.

<!-- END AWS Agent Toolkit rules -->

