variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  type        = string
}

variable "enable_github_oidc" {
  description = "Whether to create GitHub Actions OIDC provider and role (disabled if SCP explicitly denies OIDC)"
  type        = bool
  default     = false
}

variable "github_repo" {
  description = "GitHub repository format 'owner/repo' for OIDC trust"
  type        = string
  default     = "amisha-sam/student-portal"
}
