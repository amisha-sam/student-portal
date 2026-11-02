variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for RDS subnet group"
  type        = list(string)
}

variable "rds_security_group_id" {
  description = "Security group ID for RDS"
  type        = string
}

variable "db_instance_class" {
  description = "RDS instance class (free-tier eligible)"
  type        = string
  default     = "db.t4g.micro"
}

variable "db_name" {
  description = "Initial database name"
  type        = string
  default     = "portal"
}

variable "db_username" {
  description = "Master database username"
  type        = string
  default     = "portaladmin"
}

variable "postgres_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16.11"
}

variable "allocated_storage" {
  description = "Storage in GB (free-tier allows up to 20 GB)"
  type        = number
  default     = 20
}
