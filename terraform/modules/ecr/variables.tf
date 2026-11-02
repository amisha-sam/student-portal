variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "max_image_count" {
  description = "Number of images to retain in ECR lifecycle policy"
  type        = number
  default     = 3
}
