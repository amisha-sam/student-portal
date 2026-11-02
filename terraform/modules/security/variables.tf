variable "vpc_id" {
  description = "VPC ID where security groups will be created"
  type        = string
}

variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "enable_alb" {
  description = "Whether the ALB is enabled"
  type        = bool
  default     = true
}

variable "app_port" {
  description = "Port the application container listens on"
  type        = number
  default     = 8000
}
