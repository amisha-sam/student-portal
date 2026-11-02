terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote State with S3 Native State Locking (Terraform >= 1.10, no DynamoDB needed)
  backend "s3" {
    bucket       = "student-portal-tfstate-149168123176"
    key          = "envs/dev/terraform.tfstate"
    region       = "ap-southeast-2"
    profile      = "studentportalnew"
    encrypt      = true
    use_lockfile = true
  }
}
