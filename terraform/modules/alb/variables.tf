variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the ALB will be provisioned"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for the ALB"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group ID for the ALB"
  type        = string
}

variable "enable_alb" {
  description = "Whether to provision the ALB"
  type        = bool
  default     = true
}

variable "app_port" {
  description = "Port the application container listens on"
  type        = number
  default     = 8000
}
