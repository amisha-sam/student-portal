output "alb_dns_name" {
  description = "Public URL of the Application Load Balancer"
  value       = module.alb.alb_dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for Docker container images"
  value       = module.ecr.repository_url
}

output "rds_endpoint" {
  description = "PostgreSQL endpoint (private subnet)"
  value       = module.rds.db_instance_endpoint
}

output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = module.compute.asg_name
}

output "database_url_parameter" {
  description = "SSM Parameter Store path containing the database URL"
  value       = module.rds.database_url_parameter_name
}

output "ssm_session_instructions" {
  description = "Command to connect securely to the EC2 app host without SSH"
  value       = "aws ssm start-session --target <instance_id> --region ${var.aws_region} --profile ${var.aws_profile}"
}
