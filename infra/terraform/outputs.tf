output "alb_dns_name" {
  description = "ALB DNS name -- point a CNAME here if not using the Route 53 records this stack already creates."
  value       = aws_lb.this.dns_name
}

output "api_url" {
  description = "Public URL for the api service."
  value       = "https://api.${var.domain_name}"
}

output "web_url" {
  description = "Public URL for the web service."
  value       = "https://app.${var.domain_name}"
}

output "db_endpoint" {
  description = "RDS PostgreSQL endpoint (private -- only reachable from within the VPC)."
  value       = aws_db_instance.postgres.address
}

output "redis_endpoint" {
  description = "ElastiCache Redis primary endpoint (private)."
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "transcripts_bucket" {
  description = "S3 bucket name for archived source transcript/audio files."
  value       = aws_s3_bucket.transcripts.bucket
}
