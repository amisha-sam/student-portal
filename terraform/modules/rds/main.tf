resource "random_password" "db_password" {
  length  = 24
  special = false
}

resource "aws_db_subnet_group" "rds" {
  name        = "${var.project_name}-${var.environment}-rds-subnet-group"
  description = "RDS subnet group across multi-AZ private subnets"
  subnet_ids  = var.private_subnet_ids

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-subnet-group"
  }
}

resource "aws_db_instance" "postgres" {
  identifier                 = "${var.project_name}-${var.environment}-db"
  engine                     = "postgres"
  engine_version             = var.postgres_version
  instance_class             = var.db_instance_class
  allocated_storage          = var.allocated_storage
  storage_type               = "gp3"
  storage_encrypted          = true
  db_name                    = var.db_name
  username                   = var.db_username
  password                   = random_password.db_password.result
  db_subnet_group_name       = aws_db_subnet_group.rds.name
  vpc_security_group_ids     = [var.rds_security_group_id]
  publicly_accessible        = false
  multi_az                   = false
  auto_minor_version_upgrade = true
  backup_retention_period    = 1
  skip_final_snapshot        = true
  deletion_protection        = false
  apply_immediately          = true

  tags = {
    Name = "${var.project_name}-${var.environment}-postgres"
  }
}

# Store database password in SSM Parameter Store (SecureString is free)
resource "aws_ssm_parameter" "db_password" {
  name        = "/${var.project_name}/${var.environment}/db_password"
  description = "Database master password for ${var.project_name} ${var.environment}"
  type        = "SecureString"
  value       = random_password.db_password.result

  tags = {
    Name = "${var.project_name}-${var.environment}-db-password"
  }
}

# Store full connection string in SSM Parameter Store
resource "aws_ssm_parameter" "database_url" {
  name        = "/${var.project_name}/${var.environment}/database_url"
  description = "Full PostgreSQL connection URL with psycopg2 scheme"
  type        = "SecureString"
  value       = "postgresql+psycopg2://${var.db_username}:${random_password.db_password.result}@${aws_db_instance.postgres.endpoint}/${var.db_name}"

  tags = {
    Name = "${var.project_name}-${var.environment}-database-url"
  }
}
