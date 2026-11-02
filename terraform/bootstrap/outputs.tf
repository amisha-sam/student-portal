output "state_bucket_name" {
  description = "Name of the created S3 remote state bucket"
  value       = aws_s3_bucket.tfstate.id
}

output "state_bucket_arn" {
  description = "ARN of the created S3 remote state bucket"
  value       = aws_s3_bucket.tfstate.arn
}

output "state_bucket_region" {
  description = "Region where the state bucket was provisioned"
  value       = aws_s3_bucket.tfstate.region
}
