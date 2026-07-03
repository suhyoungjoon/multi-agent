from models import WizardRequest, GenerateResponse


def generate_aws(req: WizardRequest) -> GenerateResponse:
    return GenerateResponse(
        summary=_build_summary(req),
        diagram=_build_diagram(req),
        terraform=_build_terraform(req),
    )


def _build_summary(req: WizardRequest) -> str:
    comp_names = {"db": "RDS", "cache": "ElastiCache", "cdn": "CloudFront",
                  "queue": "SQS", "storage": "S3"}
    comps = ", ".join(comp_names.get(c, c) for c in req.components) or "없음"
    ha_text = "다중 가용 영역(Multi-AZ)" if req.scale.ha else "단일 가용 영역"
    return (
        f"AWS 기반 {req.app_type} 아키텍처입니다. "
        f"사용 컴포넌트: {comps}. "
        f"트래픽 규모: {req.scale.traffic}. "
        f"가용성: {ha_text}. "
        f"VPC + Subnet + Security Group으로 네트워크를 구성하고, "
        f"EC2/ALB로 애플리케이션을 서빙합니다."
    )


def _build_diagram(req: WizardRequest) -> str:
    lines = ["graph TD", "  Internet([Internet]) --> ALB[ALB]",
             "  ALB --> EC2[EC2 / App Server]", "  EC2 --> VPC[VPC + Subnet]"]
    if "db" in req.components:
        lines.append("  EC2 --> RDS[(RDS)]")
    if "cache" in req.components:
        lines.append("  EC2 --> Cache[(ElastiCache)]")
    if "cdn" in req.components:
        lines.insert(1, "  Internet --> CDN[CloudFront CDN]")
    if "queue" in req.components:
        lines.append("  EC2 --> SQS[SQS Queue]")
    if "storage" in req.components:
        lines.append("  EC2 --> S3[(S3 Bucket)]")
    return "\n".join(lines)


def _build_terraform(req: WizardRequest) -> dict[str, str]:
    main_blocks = [_TF_VPC, _TF_ALB, _TF_EC2]
    if "db" in req.components:
        main_blocks.append(_tf_rds(req.scale.ha))
    if "cache" in req.components:
        main_blocks.append(_TF_ELASTICACHE)
    if "cdn" in req.components:
        main_blocks.append(_TF_CLOUDFRONT)
    if "queue" in req.components:
        main_blocks.append(_TF_SQS)
    if "storage" in req.components:
        main_blocks.append(_TF_S3)
    if req.scale.multi_region:
        main_blocks.append(_TF_MULTI_REGION_COMMENT)
    return {
        "main.tf": "\n\n".join(main_blocks),
        "variables.tf": _TF_VARIABLES,
        "outputs.tf": _TF_OUTPUTS,
    }


def _tf_rds(ha: bool) -> str:
    multi_az_line = "\n  multi_az = true" if ha else ""
    return f'''\
resource "aws_db_instance" "main" {{
  engine                     = var.db_engine
  instance_class             = var.db_instance_class
  username                   = var.db_username
  password                   = var.db_password
  final_snapshot_identifier  = var.db_final_snapshot_identifier{multi_az_line}
}}'''


_TF_VPC = '''\
resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
  tags = { Name = var.project_name }
}

resource "aws_subnet" "public" {
  vpc_id     = aws_vpc.main.id
  cidr_block = var.public_subnet_cidr
}

resource "aws_security_group" "app" {
  vpc_id = aws_vpc.main.id
  ingress { from_port = 80  to_port = 80  protocol = "tcp" cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 443 to_port = 443 protocol = "tcp" cidr_blocks = ["0.0.0.0/0"] }
  egress  { from_port = 0   to_port = 0   protocol = "-1"  cidr_blocks = ["0.0.0.0/0"] }
}'''

_TF_ALB = '''\
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.app.id]
  subnets            = [aws_subnet.public.id]
}

resource "aws_lb_target_group" "main" {
  name     = "${var.project_name}-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}'''

_TF_EC2 = '''\
resource "aws_instance" "app" {
  ami                    = var.ec2_ami
  instance_type          = var.ec2_instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  tags = { Name = "${var.project_name}-app" }
}'''

_TF_MULTI_REGION_COMMENT = '''\
# 멀티리전 구성 안내
# multi_region=true 선택 시 아래 사항을 수동으로 추가하세요:
#   - aws_route53_record: 지연 기반(latency) 또는 지리적(geolocation) 라우팅
#   - 각 리전별 VPC/ALB/EC2 모듈 복제 (module "region_*" { source = "./modules/region" })
#   - aws_rds_global_cluster: RDS Aurora Global Database (멀티리전 DB 복제)
#   - aws_cloudfront_distribution: 엣지 캐싱으로 글로벌 응답 속도 개선'''

_TF_ELASTICACHE = '''\
resource "aws_elasticache_cluster" "main" {
  cluster_id      = "${var.project_name}-cache"
  engine          = "redis"
  node_type       = var.cache_node_type
  num_cache_nodes = 1
}'''

_TF_CLOUDFRONT = '''\
resource "aws_cloudfront_distribution" "main" {
  enabled = true
  origin {
    domain_name = var.origin_domain
    origin_id   = "main-origin"
  }
  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "main-origin"
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values { query_string = false; cookies { forward = "none" } }
  }
  restrictions { geo_restriction { restriction_type = "none" } }
  viewer_certificate { cloudfront_default_certificate = true }
}'''

_TF_SQS = '''\
resource "aws_sqs_queue" "main" {
  name = "${var.project_name}-queue"
}'''

_TF_S3 = '''\
resource "aws_s3_bucket" "main" {
  bucket = var.s3_bucket_name
}'''

_TF_VARIABLES = '''\
variable "project_name"                { type = string }
variable "aws_region"                  { type = string  default = "ap-northeast-2" }
variable "vpc_cidr"                    { type = string  default = "10.0.0.0/16" }
variable "public_subnet_cidr"          { type = string  default = "10.0.1.0/24" }
variable "ec2_ami"                     { type = string }
variable "ec2_instance_type"           { type = string  default = "t3.micro" }
variable "db_engine"                   { type = string  default = "postgres" }
variable "db_instance_class"           { type = string  default = "db.t3.micro" }
variable "db_username"                 { type = string }
variable "db_password"                 { type = string  sensitive = true }
variable "db_final_snapshot_identifier" { type = string  default = "final-snapshot" }
variable "cache_node_type"             { type = string  default = "cache.t3.micro" }
variable "origin_domain"               { type = string }
variable "s3_bucket_name"              { type = string  default = "" }'''

_TF_OUTPUTS = '''\
output "vpc_id"    { value = aws_vpc.main.id }
output "subnet_id" { value = aws_subnet.public.id }
output "alb_dns"   { value = aws_lb.main.dns_name }'''
