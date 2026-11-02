variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where instances reside"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for the ASG"
  type        = list(string)
}

variable "app_security_group_id" {
  description = "Security group ID for the app host"
  type        = string
}

variable "instance_profile_name" {
  description = "IAM instance profile name for EC2"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type (free-tier eligible Graviton2)"
  type        = string
  default     = "t4g.micro"
}

variable "target_group_arn" {
  description = "ARN of the ALB target group (optional if ALB disabled)"
  type        = string
  default     = null
}

variable "enable_alb" {
  description = "Whether the ALB is enabled"
  type        = bool
  default     = true
}

variable "app_port" {
  description = "Application port"
  type        = number
  default     = 8000
}
