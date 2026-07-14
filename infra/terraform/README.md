# Terraform sketch — AWS productionization path

This is a **sketch, not a deployment**. Nothing here has been applied
against a real AWS account, and it isn't part of this submission's CI or
test suite. It exists to document, in reviewable code rather than prose
alone, what standing this system up on a hyperscaler would actually
involve — the resources, the trust boundaries, and the places a real
deployment would need real decisions (instance sizing, autoscaling
policies, alerting thresholds) that a take-home submission doesn't need
to make. See the root `README.md`'s "Productionizing this" section for
the fuller discussion this sketch supports.

## What's here

- `main.tf` — VPC (public + private subnets across two AZs), an ALB
  routing by hostname to two ECS Fargate services (`api`, `web`), an RDS
  PostgreSQL instance (pgvector-compatible engine version) in the private
  subnets, an ElastiCache Redis replication group, and an S3 bucket for
  archiving original uploaded transcript/audio files.
- `variables.tf` — every input a real `terraform apply` would need
  (region, image tags, instance sizes, secret ARNs), with no defaults for
  anything that should never have one (there's no `db_password` variable
  with a placeholder default — see "Secrets" below).
- `outputs.tf` — the ALB DNS name and RDS/Redis endpoints a deployer would
  actually need after applying this.

## What's deliberately stubbed, not built

- **No state backend configured.** A real deployment needs a remote
  backend (S3 + DynamoDB lock table, or Terraform Cloud) — omitted here
  since this sketch is never actually applied.
- **No autoscaling policies, CloudWatch alarms, or WAF.** A real
  production deployment needs all three; sizing and thresholds for them
  depend on real traffic data this project has none of.
- **Secrets are referenced, never generated.** `GEMINI_API_KEY`,
  `HF_TOKEN`, and database credentials are modeled as AWS Secrets Manager
  ARNs the ECS task definitions pull from at runtime (`secrets` blocks,
  never plaintext environment variables) — but this sketch doesn't create
  those secrets. A real deployment provisions them out-of-band and passes
  the ARNs in as variables.
- **No CI/CD wiring to actually run `terraform plan`/`apply`.** This
  project's real CI (`.github/workflows/`) lints/tests/builds Docker
  images; it stops there. Standing up a `terraform plan` gate on PRs
  touching `infra/` is a natural next step, not done here.
- **Single region, no DR/multi-AZ RDS failover.** `multi_az = false` by
  default — flipping it is a one-line change once real availability
  requirements exist to justify the added cost.

## Why ECS Fargate over EC2, EKS, or a PaaS

Fargate removes host patching/capacity management entirely for two
stateless containers (`api`, `web`) with no unusual compute requirements
(the CPU-only ML inference in the audio path, see `docs/adr/0012`, runs
fine on Fargate's standard vCPU/memory tiers). EKS's added operational
surface (cluster control-plane management, node group lifecycle) isn't
justified for two services; a PaaS (Elastic Beanstalk, App Runner) would
fit too, but ECS Fargate is the more directly JD-aligned choice and the
one with the clearest ECS+RDS+ElastiCache+ALB reference architecture to
sketch against.

## Why RDS Postgres, not Aurora

Aurora's main advantages (fast storage-layer replication, serverless
scale-to-zero) don't move the needle for pgvector specifically — Aurora
PostgreSQL's pgvector support has historically lagged plain RDS
PostgreSQL's, and this system's storage engine choice (`docs/adr/0004`)
already leans on pgvector being a first-class, unsurprising Postgres
extension. Plain RDS PostgreSQL is the safer, more directly-portable
choice from the local `docker-compose.yml` Postgres instance this
sketch's `db_instance_class` variable is sized to approximate.
