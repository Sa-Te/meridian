# AWS productionization sketch for Meridian. See README.md in this
# directory for what's deliberately stubbed and why -- this has never
# been applied against a real account. No backend block: add a remote
# state backend (S3 + DynamoDB lock table) before ever running this for
# real.

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = "meridian-${var.environment}"
  tags = {
    Project     = "meridian"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# --- Networking -------------------------------------------------------------
# Two-AZ public/private split: the ALB and NAT gateways live in public
# subnets; ECS tasks, RDS, and ElastiCache live in private subnets with no
# route to the internet except outbound via NAT (for pulling model weights
# on first run -- see docs/adr/0012 -- and calling the Gemini/HF APIs).

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${local.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name_prefix}-igw" })
}

resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(local.tags, { Name = "${local.name_prefix}-public-${count.index}" })
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.this.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  availability_zone = var.availability_zones[count.index]
  tags              = merge(local.tags, { Name = "${local.name_prefix}-private-${count.index}" })
}

resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"
  tags   = merge(local.tags, { Name = "${local.name_prefix}-nat-eip-${count.index}" })
}

resource "aws_nat_gateway" "this" {
  count         = length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = merge(local.tags, { Name = "${local.name_prefix}-nat-${count.index}" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(local.tags, { Name = "${local.name_prefix}-public-rt" })
}

resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[count.index].id
  }
  tags = merge(local.tags, { Name = "${local.name_prefix}-private-rt-${count.index}" })
}

resource "aws_route_table_association" "public" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# --- Security groups ---------------------------------------------------------

resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  vpc_id      = aws_vpc.this.id
  ingress {
    description = "HTTPS from the internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${local.name_prefix}-ecs-"
  vpc_id      = aws_vpc.this.id
  ingress {
    description     = "From the ALB only"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "db" {
  name_prefix = "${local.name_prefix}-db-"
  vpc_id      = aws_vpc.this.id
  ingress {
    description     = "Postgres from ECS tasks only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
  tags = local.tags
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.name_prefix}-redis-"
  vpc_id      = aws_vpc.this.id
  ingress {
    description     = "Redis from ECS tasks only"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
  tags = local.tags
}

# --- RDS PostgreSQL (pgvector) -----------------------------------------------
# See docs/adr/0004 for why pgvector-in-Postgres rather than a dedicated
# vector database, and README.md for why RDS over Aurora. pgvector itself
# still needs `CREATE EXTENSION vector;` run once against this instance --
# not automated here, same as the local docker-compose setup relies on the
# pgvector/pgvector Docker image having it precompiled, not Terraform.

resource "aws_db_subnet_group" "this" {
  name       = "${local.name_prefix}-db"
  subnet_ids = aws_subnet.private[*].id
  tags       = local.tags
}

# Master credentials are read from an externally-provisioned Secrets
# Manager secret (var.db_credentials_secret_arn) -- never a plaintext
# variable or a value Terraform itself generates. The secret is expected
# to hold a JSON object shaped {"username": "...", "password": "..."};
# provisioning it is a deployer's job, out of band (see README.md's
# "Secrets" section).
data "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = var.db_credentials_secret_arn
}

resource "aws_db_instance" "postgres" {
  identifier                = "${local.name_prefix}-db"
  engine                    = "postgres"
  engine_version            = var.db_engine_version
  instance_class            = var.db_instance_class
  allocated_storage         = var.db_allocated_storage_gb
  storage_encrypted         = true
  db_subnet_group_name      = aws_db_subnet_group.this.name
  vpc_security_group_ids    = [aws_security_group.db.id]
  multi_az                  = var.db_multi_az
  publicly_accessible       = false
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name_prefix}-db-final"
  username                  = jsondecode(data.aws_secretsmanager_secret_version.db_credentials.secret_string)["username"]
  password                  = jsondecode(data.aws_secretsmanager_secret_version.db_credentials.secret_string)["password"]
  tags                      = local.tags
}

# --- ElastiCache Redis --------------------------------------------------------

resource "aws_elasticache_subnet_group" "this" {
  name       = "${local.name_prefix}-redis"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name_prefix}-redis"
  description                = "Meridian caching and lightweight rate limiting"
  engine                     = "redis"
  node_type                  = var.redis_node_type
  num_cache_clusters         = 1
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.redis.id]
  automatic_failover_enabled = false # single node -- flip with num_cache_clusters > 1 for real HA
  tags                       = local.tags
}

# --- S3: archived source transcripts/audio -----------------------------------
# Today the app stores raw_text in Postgres and never persists the
# original uploaded file. A production deployment should archive the
# original (audio especially, per docs/adr/0012) for reprocessing if the
# transcription/diarization pipeline ever improves.

resource "aws_s3_bucket" "transcripts" {
  bucket = "${local.name_prefix}-transcripts"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "transcripts" {
  bucket = aws_s3_bucket.transcripts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "transcripts" {
  bucket                  = aws_s3_bucket.transcripts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- ECS ----------------------------------------------------------------------

resource "aws_ecs_cluster" "this" {
  name = local.name_prefix
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = local.tags
}

resource "aws_iam_role" "ecs_execution" {
  name_prefix        = "${local.name_prefix}-exec-"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# api task: pulls GEMINI_API_KEY/HF_TOKEN/DB creds from Secrets Manager at
# launch (the `secrets` block below), never as plaintext task-def
# environment variables.
resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_task_cpu
  memory                   = var.api_task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([
    {
      name         = "api"
      image        = var.api_image
      essential    = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LLM_PROVIDER", value = "gemini" },
        { name = "EMBEDDING_PROVIDER", value = "local" },
        { name = "DATABASE_URL", value = "postgresql+asyncpg://meridian:@${aws_db_instance.postgres.address}:5432/meridian" },
        { name = "REDIS_URL", value = "redis://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0" },
      ]
      secrets = concat(
        [
          { name = "GEMINI_API_KEY", valueFrom = var.gemini_api_key_secret_arn },
          { name = "DB_PASSWORD", valueFrom = var.db_credentials_secret_arn },
        ],
        var.hf_token_secret_arn == null ? [] : [{ name = "HF_TOKEN", valueFrom = var.hf_token_secret_arn }]
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_ecs_task_definition" "web" {
  family                   = "${local.name_prefix}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.web_task_cpu
  memory                   = var.web_task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([
    {
      name         = "web"
      image        = var.web_image
      essential    = true
      portMappings = [{ containerPort = 3000, protocol = "tcp" }]
      environment = [
        { name = "NEXT_PUBLIC_API_URL", value = "https://api.${var.domain_name}" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.web.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "web"
        }
      }
    }
  ])

  tags = local.tags
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name_prefix}-api"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "web" {
  name              = "/ecs/${local.name_prefix}-web"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]
  tags       = local.tags
}

resource "aws_ecs_service" "web" {
  name            = "${local.name_prefix}-web"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = var.web_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web.arn
    container_name   = "web"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.https]
  tags       = local.tags
}

# --- Application Load Balancer: host-based routing ---------------------------
# app.<domain> -> web, api.<domain> -> api. Host-based rather than
# path-based routing avoids any collision between web's own Next.js
# routes and the api's paths -- the web app calls the api directly from
# the browser (NEXT_PUBLIC_API_URL, see docs/adr/0014), so the api target
# group must be reachable from the public internet too, not just from web.

resource "aws_lb" "this" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  tags               = local.tags
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name_prefix}-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"
  health_check {
    path = "/health"
  }
  tags = local.tags
}

resource "aws_lb_target_group" "web" {
  name        = "${local.name_prefix}-web"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.this.id
  target_type = "ip"
  health_check {
    path = "/"
  }
  tags = local.tags
}

resource "aws_acm_certificate" "this" {
  domain_name               = var.domain_name
  subject_alternative_names = ["app.${var.domain_name}", "api.${var.domain_name}"]
  validation_method         = "DNS"
  tags                      = local.tags
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = aws_acm_certificate.this.arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  condition {
    host_header {
      values = ["api.${var.domain_name}"]
    }
  }
}

resource "aws_route53_record" "web" {
  zone_id = var.route53_zone_id
  name    = "app.${var.domain_name}"
  type    = "A"
  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "api" {
  zone_id = var.route53_zone_id
  name    = "api.${var.domain_name}"
  type    = "A"
  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}
