# Query 2 available AZs in the selected region
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  selected_azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

# 1. Networking: VPC with 2 public & 2 private subnets, no NAT gateway ($0 cost)
module "vpc" {
  source             = "../../modules/vpc"
  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = local.selected_azs
}

# 2. Security Groups: ALB, App Host, and isolated RDS (no SSH port open)
module "security" {
  source       = "../../modules/security"
  project_name = var.project_name
  environment  = var.environment
  vpc_id       = module.vpc.vpc_id
  enable_alb   = var.enable_alb
  app_port     = var.app_port
}

# 3. Registry: ECR repository with scan on push and automated cleanup lifecycle
module "ecr" {
  source          = "../../modules/ecr"
  project_name    = var.project_name
  environment     = var.environment
  max_image_count = 3
}

# 4. IAM: EC2 Instance Profile with SSM Core, ECR pull, and Parameter Store read
module "iam" {
  source             = "../../modules/iam"
  project_name       = var.project_name
  environment        = var.environment
  ecr_repository_arn = module.ecr.repository_arn
}

# 5. Database: Encrypted PostgreSQL 16 on db.t4g.micro in private subnets
module "rds" {
  source                = "../../modules/rds"
  project_name          = var.project_name
  environment           = var.environment
  private_subnet_ids    = module.vpc.private_subnet_ids
  rds_security_group_id = module.security.rds_security_group_id
  db_instance_class     = var.db_instance_class
  db_name               = "portal"
  db_username           = "portaladmin"
  postgres_version      = "16.11"
  allocated_storage     = 20
}

# 6. Load Balancing: Application Load Balancer with healthcheck on /health
module "alb" {
  source                = "../../modules/alb"
  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  public_subnet_ids     = module.vpc.public_subnet_ids
  alb_security_group_id = module.security.alb_security_group_id
  enable_alb            = var.enable_alb
  app_port              = var.app_port
}

# 7. Compute: Self-healing ASG (min=1, max=1) with Graviton2 t4g.micro and IMDSv2
module "compute" {
  source                = "../../modules/compute"
  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  public_subnet_ids     = module.vpc.public_subnet_ids
  app_security_group_id = module.security.app_security_group_id
  instance_profile_name = module.iam.instance_profile_name
  instance_type         = var.instance_type
  enable_alb            = var.enable_alb
  target_group_arn      = module.alb.target_group_arn
}
