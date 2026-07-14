variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name, used to prefix/tag every resource."
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC this stack creates."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "Two AZs to spread public/private subnets across."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# --- Container images ---
# Built and pushed by CI (.github/workflows/ci.yml already tags
# meridian-api/meridian-web with the commit SHA -- see docs/adr/0015) to
# an ECR repository this sketch does not itself create.

variable "api_image" {
  description = "Fully-qualified ECR image URI for the api service, e.g. <account>.dkr.ecr.<region>.amazonaws.com/meridian-api:<sha>."
  type        = string
}

variable "web_image" {
  description = "Fully-qualified ECR image URI for the web service."
  type        = string
}

# --- Compute sizing ---
# Fargate task sizing for two stateless services with no unusual compute
# requirements -- see README.md's "Why ECS Fargate" note. faster-whisper/
# pyannote.audio (docs/adr/0012) run CPU-only and fit comfortably in the
# api service's own task, not a separate compute pool.

variable "api_task_cpu" {
  description = "Fargate task vCPU units for the api service (1024 = 1 vCPU)."
  type        = number
  default     = 1024
}

variable "api_task_memory" {
  description = "Fargate task memory (MiB) for the api service."
  type        = number
  default     = 2048
}

variable "web_task_cpu" {
  description = "Fargate task vCPU units for the web service."
  type        = number
  default     = 512
}

variable "web_task_memory" {
  description = "Fargate task memory (MiB) for the web service."
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Number of api tasks to run. No autoscaling policy is configured (see README.md) -- this is a fixed count."
  type        = number
  default     = 2
}

variable "web_desired_count" {
  description = "Number of web tasks to run."
  type        = number
  default     = 2
}

# --- Database ---

variable "db_instance_class" {
  description = "RDS instance class. db.t4g.medium approximates the local docker-compose Postgres container's resources; size up once real query load exists to measure against."
  type        = string
  default     = "db.t4g.medium"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version. Must support the pgvector extension (16.x on RDS does)."
  type        = string
  default     = "16.4"
}

variable "db_allocated_storage_gb" {
  description = "RDS allocated storage in GB."
  type        = number
  default     = 50
}

variable "db_multi_az" {
  description = "Whether RDS runs multi-AZ (real failover). Off by default -- see README.md."
  type        = bool
  default     = false
}

# --- Cache ---

variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"
}

# --- Secrets ---
# Referenced, never created or defaulted -- see README.md's "Secrets"
# section. Provisioning these ARNs is a deployer's job, out of band.

variable "gemini_api_key_secret_arn" {
  description = "ARN of an AWS Secrets Manager secret holding GEMINI_API_KEY."
  type        = string
}

variable "hf_token_secret_arn" {
  description = "ARN of an AWS Secrets Manager secret holding HF_TOKEN (optional -- only required if the audio ingestion path, docs/adr/0012, is enabled)."
  type        = string
  default     = null
}

variable "db_credentials_secret_arn" {
  description = "ARN of an AWS Secrets Manager secret holding the RDS master username/password."
  type        = string
}

# --- DNS ---

variable "route53_zone_id" {
  description = "Hosted zone id to create app/api DNS records in."
  type        = string
}

variable "domain_name" {
  description = "Base domain, e.g. meridian.example.com -- app.<domain_name> and api.<domain_name> are created."
  type        = string
}
