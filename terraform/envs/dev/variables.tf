variable "aws_region" {
  description = "AWS Region to deploy resources into"
  type        = string
  default     = "ap-southeast-2"
}

variable "aws_profile" {
  description = "AWS CLI profile name for authentication"
  type        = string
  default     = "studentportalnew"
}

variable "project_name" {
  description = "Project name tag and naming prefix"
  type        = string
  default     = "student-portal"
}

variable "environment" {
  description = "Environment stage (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "enable_alb" {
  description = "Toggle Application Load Balancer (true for demos, false while idle to conserve credits)"
  type        = bool
  default     = true
}

variable "instance_type" {
  description = "EC2 instance type for app host (free-tier eligible Graviton2)"
  type        = string
  default     = "t4g.micro"
}

variable "db_instance_class" {
  description = "RDS instance class (free-tier eligible Graviton2)"
  type        = string
  default     = "db.t4g.micro"
}

variable "app_port" {
  description = "Container port for the student portal Flask application"
  type        = number
  default     = 8000
}
