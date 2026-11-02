data "aws_ssm_parameter" "al2023_arm64" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

# User Data script executed on instance startup
locals {
  user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail

    echo "=== Starting Student Portal App Host Initialization ==="

    # 1. Update OS packages & install Docker
    dnf update -y
    dnf install -y docker git

    # 2. Start and enable Docker
    systemctl start docker
    systemctl enable docker
    usermod -aG docker ec2-user

    # 3. Ensure AWS Systems Manager (SSM) agent is active
    systemctl enable amazon-ssm-agent
    systemctl restart amazon-ssm-agent

    # 4. Prepare directory for app deployment & Ansible
    mkdir -p /opt/student-portal
    chown -R ec2-user:ec2-user /opt/student-portal

    echo "=== Host Initialization Complete ==="
  EOF
}

resource "aws_launch_template" "app" {
  name_prefix   = "${var.project_name}-${var.environment}-lt-"
  image_id      = data.aws_ssm_parameter.al2023_arm64.value
  instance_type = var.instance_type

  iam_instance_profile {
    name = var.instance_profile_name
  }

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [var.app_security_group_id]
  }

  user_data = base64encode(local.user_data)

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  # Require IMDSv2 for high security
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name        = "${var.project_name}-${var.environment}-app-host"
      Project     = var.project_name
      Environment = var.environment
      Role        = "app-host"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "app" {
  name_prefix         = "${var.project_name}-${var.environment}-asg-"
  vpc_zone_identifier = var.public_subnet_ids

  min_size         = 1
  max_size         = 1
  desired_capacity = 1

  health_check_type         = var.enable_alb && var.target_group_arn != null ? "ELB" : "EC2"
  health_check_grace_period = 900

  target_group_arns = var.enable_alb && var.target_group_arn != null ? [var.target_group_arn] : []

  launch_template {
    id      = aws_launch_template.app.id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 0
    }
  }

  lifecycle {
    create_before_destroy = true
  }

  tag {
    key                 = "Name"
    value               = "${var.project_name}-${var.environment}-asg-instance"
    propagate_at_launch = true
  }
}
