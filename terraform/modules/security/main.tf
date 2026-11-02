# ALB Security Group: Accepts HTTP on port 80 from the internet
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-${var.environment}-alb-sg"
  description = "Allows inbound HTTP traffic to the ALB"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Outbound to all destinations"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-alb-sg"
  }
}

# App Host Security Group: Strictly allows traffic from ALB (or direct if ALB disabled). NO SSH OPEN.
resource "aws_security_group" "app" {
  name        = "${var.project_name}-${var.environment}-app-sg"
  description = "Security group for student portal app EC2 host (SSM managed, no SSH)"
  vpc_id      = var.vpc_id

  egress {
    description = "Outbound internet access for ECR, SSM, and OS updates"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-app-sg"
  }
}

# Ingress from ALB to App
resource "aws_security_group_rule" "app_from_alb" {
  count                    = var.enable_alb ? 1 : 0
  type                     = "ingress"
  description              = "Allow traffic from ALB on app port"
  from_port                = var.app_port
  to_port                  = var.app_port
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.app.id
}

# Fallback ingress directly to App if ALB is disabled (cost saving mode)
resource "aws_security_group_rule" "app_direct" {
  count             = var.enable_alb ? 0 : 1
  type              = "ingress"
  description       = "Direct app access when ALB is disabled"
  from_port         = var.app_port
  to_port           = var.app_port
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.app.id
}

# RDS Security Group: Accepts traffic on 5432 strictly from the App security group
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-${var.environment}-rds-sg"
  description = "Isolates PostgreSQL to App instances only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from App host only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    description = "Local VPC egress only"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/16"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-sg"
  }
}
