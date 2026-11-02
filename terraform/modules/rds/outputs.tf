output "db_instance_id" {
  description = "ID of the RDS instance"
  value       = aws_db_instance.postgres.id
}

output "db_instance_endpoint" {
  description = "Endpoint of the RDS instance"
  value       = aws_db_instance.postgres.endpoint
}

output "db_instance_address" {
  description = "Address (hostname) of the RDS instance"
  value       = aws_db_instance.postgres.address
}

output "db_instance_port" {
  description = "Port of the RDS instance"
  value       = aws_db_instance.postgres.port
}

output "database_url_parameter_name" {
  description = "SSM parameter name storing the full database URL"
  value       = aws_ssm_parameter.database_url.name
}
