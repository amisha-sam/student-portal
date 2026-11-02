variable "aws_region" {
  description = "AWS region for the S3 remote state bucket"
  type        = string
  default     = "ap-southeast-2"
}

variable "aws_profile" {
  description = "AWS CLI profile name for authentication"
  type        = string
  default     = "studentportalnew"
}

variable "project_name" {
  description = "Project name tag and prefix"
  type        = string
  default     = "student-portal"
}
