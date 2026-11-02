output "alb_dns_name" {
  description = "DNS name of the application load balancer"
  value       = var.enable_alb ? aws_lb.main[0].dns_name : null
}

output "alb_arn" {
  description = "ARN of the application load balancer"
  value       = var.enable_alb ? aws_lb.main[0].arn : null
}

output "target_group_arn" {
  description = "ARN of the application target group"
  value       = var.enable_alb ? aws_lb_target_group.app[0].arn : null
}
