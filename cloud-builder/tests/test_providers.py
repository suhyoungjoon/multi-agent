import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import WizardRequest, ScaleConfig
from providers.aws import generate_aws
from providers.azure import generate_azure


def _make_req(**kwargs):
    defaults = dict(
        provider="aws", app_type="web",
        components=["db", "cache"],
        scale=ScaleConfig(traffic="medium", ha=True, multi_region=False),
        notes="",
    )
    defaults.update(kwargs)
    return WizardRequest(**defaults)


def test_aws_summary_contains_provider():
    resp = generate_aws(_make_req())
    assert "AWS" in resp.summary


def test_aws_diagram_is_mermaid():
    resp = generate_aws(_make_req())
    assert resp.diagram.startswith("graph TD")


def test_aws_terraform_has_required_files():
    resp = generate_aws(_make_req())
    assert "main.tf" in resp.terraform
    assert "variables.tf" in resp.terraform
    assert "outputs.tf" in resp.terraform


def test_aws_db_component_adds_rds():
    resp = generate_aws(_make_req(components=["db"]))
    assert "aws_db_instance" in resp.terraform["main.tf"]


def test_aws_cache_component_adds_elasticache():
    resp = generate_aws(_make_req(components=["cache"]))
    assert "aws_elasticache_cluster" in resp.terraform["main.tf"]


def test_aws_cdn_component_adds_cloudfront():
    resp = generate_aws(_make_req(components=["cdn"]))
    assert "aws_cloudfront_distribution" in resp.terraform["main.tf"]


def test_aws_no_components_has_only_vpc():
    resp = generate_aws(_make_req(components=[]))
    assert "aws_vpc" in resp.terraform["main.tf"]
    assert "aws_db_instance" not in resp.terraform["main.tf"]


# Azure tests

def _make_azure_req(**kwargs):
    defaults = dict(
        provider="azure", app_type="api",
        components=["db"],
        scale=ScaleConfig(traffic="low", ha=False, multi_region=False),
        notes="",
    )
    defaults.update(kwargs)
    return WizardRequest(**defaults)


def test_azure_summary_contains_provider():
    resp = generate_azure(_make_azure_req())
    assert "Azure" in resp.summary


def test_azure_diagram_is_mermaid():
    resp = generate_azure(_make_azure_req())
    assert resp.diagram.startswith("graph TD")


def test_azure_terraform_has_required_files():
    resp = generate_azure(_make_azure_req())
    assert "main.tf" in resp.terraform
    assert "variables.tf" in resp.terraform
    assert "outputs.tf" in resp.terraform


def test_azure_db_adds_sql():
    resp = generate_azure(_make_azure_req(components=["db"]))
    assert "azurerm_mssql_server" in resp.terraform["main.tf"]


def test_azure_cache_adds_redis():
    resp = generate_azure(_make_azure_req(components=["cache"]))
    assert "azurerm_redis_cache" in resp.terraform["main.tf"]


def test_azure_storage_adds_account():
    resp = generate_azure(_make_azure_req(components=["storage"]))
    assert "azurerm_storage_account" in resp.terraform["main.tf"]


# ── AWS 신규: ALB + EC2 항상 포함 ────────────────────────────────────────────

def test_aws_terraform_always_includes_alb():
    resp = generate_aws(_make_req(components=[]))
    tf = resp.terraform["main.tf"]
    assert "aws_lb" in tf
    assert "aws_lb_listener" in tf
    assert "aws_lb_target_group" in tf


def test_aws_terraform_always_includes_ec2():
    resp = generate_aws(_make_req(components=[]))
    assert "aws_instance" in resp.terraform["main.tf"]


# ── AWS 신규: HA → multi_az ──────────────────────────────────────────────────

def test_aws_ha_true_db_has_multi_az():
    req = _make_req(
        components=["db"],
        scale=ScaleConfig(traffic="medium", ha=True, multi_region=False),
    )
    assert "multi_az = true" in generate_aws(req).terraform["main.tf"]


def test_aws_ha_false_db_no_multi_az():
    req = _make_req(
        components=["db"],
        scale=ScaleConfig(traffic="medium", ha=False, multi_region=False),
    )
    assert "multi_az" not in generate_aws(req).terraform["main.tf"]


# ── AWS 신규: multi_region → 주석 ────────────────────────────────────────────

def test_aws_multi_region_true_has_comment():
    req = _make_req(scale=ScaleConfig(traffic="medium", ha=False, multi_region=True))
    assert "multi" in generate_aws(req).terraform["main.tf"].lower()
    assert "#" in generate_aws(req).terraform["main.tf"]


def test_aws_multi_region_false_no_comment():
    req = _make_req(scale=ScaleConfig(traffic="medium", ha=False, multi_region=False))
    # multi_region=False면 멀티리전 주석 없음
    tf = generate_aws(req).terraform["main.tf"]
    assert "multi-region" not in tf.lower()


# ── AWS 낮음: final_snapshot_identifier, CloudFront origin 방어 ───────────────

def test_aws_rds_uses_final_snapshot_identifier_not_skip():
    resp = generate_aws(_make_req(components=["db"]))
    tf = resp.terraform["main.tf"]
    assert "skip_final_snapshot" not in tf
    assert "final_snapshot_identifier" in tf


def test_aws_cloudfront_origin_domain_not_empty_literal():
    resp = generate_aws(_make_req(components=["cdn"]))
    tf = resp.terraform["main.tf"]
    # 빈 문자열 default("") 대신 변수 참조만 있어야 함
    assert 'domain_name = ""' not in tf
    assert "var.origin_domain" in tf


# ── Azure 신규: CDN 리소스 ────────────────────────────────────────────────────

def test_azure_cdn_adds_cdn_profile():
    resp = generate_azure(_make_azure_req(components=["cdn"]))
    assert "azurerm_cdn_profile" in resp.terraform["main.tf"]


def test_azure_cdn_adds_cdn_endpoint():
    resp = generate_azure(_make_azure_req(components=["cdn"]))
    assert "azurerm_cdn_endpoint" in resp.terraform["main.tf"]


def test_azure_no_cdn_no_cdn_profile():
    resp = generate_azure(_make_azure_req(components=[]))
    assert "azurerm_cdn_profile" not in resp.terraform["main.tf"]


# ── Azure 신규: App Service 항상 포함 ────────────────────────────────────────

def test_azure_terraform_always_includes_app_service_plan():
    resp = generate_azure(_make_azure_req(components=[]))
    assert "azurerm_app_service_plan" in resp.terraform["main.tf"]


def test_azure_terraform_always_includes_app_service():
    resp = generate_azure(_make_azure_req(components=[]))
    assert "azurerm_app_service" in resp.terraform["main.tf"]


# ── Azure 낮음: mssql_server 교체 ────────────────────────────────────────────

def test_azure_db_uses_mssql_server():
    resp = generate_azure(_make_azure_req(components=["db"]))
    tf = resp.terraform["main.tf"]
    assert "azurerm_mssql_server" in tf
    assert "azurerm_sql_server" not in tf


# ── traffic → AWS 인스턴스 크기 분기 ─────────────────────────────────────────

def _make_req_traffic(traffic, **kwargs):
    return _make_req(
        scale=ScaleConfig(traffic=traffic, ha=False, multi_region=False),
        **kwargs,
    )


def test_aws_low_traffic_ec2_type_small():
    tf = generate_aws(_make_req_traffic("low")).terraform["variables.tf"]
    assert "t3.small" in tf


def test_aws_medium_traffic_ec2_type_large():
    tf = generate_aws(_make_req_traffic("medium")).terraform["variables.tf"]
    assert "t3.large" in tf


def test_aws_high_traffic_ec2_type_xlarge():
    tf = generate_aws(_make_req_traffic("high")).terraform["variables.tf"]
    assert "t3.xlarge" in tf


def test_aws_traffic_ec2_sizes_are_distinct():
    low  = generate_aws(_make_req_traffic("low")).terraform["variables.tf"]
    med  = generate_aws(_make_req_traffic("medium")).terraform["variables.tf"]
    high = generate_aws(_make_req_traffic("high")).terraform["variables.tf"]
    # 세 traffic 레벨이 모두 다른 default 값을 가져야 함
    assert low != med
    assert med != high


def test_aws_low_traffic_db_class_micro():
    tf = generate_aws(_make_req_traffic("low", components=["db"])).terraform["variables.tf"]
    assert "db.t3.micro" in tf


def test_aws_medium_traffic_db_class_medium():
    tf = generate_aws(_make_req_traffic("medium", components=["db"])).terraform["variables.tf"]
    assert "db.t3.medium" in tf


def test_aws_high_traffic_db_class_large():
    tf = generate_aws(_make_req_traffic("high", components=["db"])).terraform["variables.tf"]
    assert "db.t3.large" in tf


# ── traffic → Azure App Service SKU 분기 ─────────────────────────────────────

def _make_azure_req_traffic(traffic, **kwargs):
    return _make_azure_req(
        scale=ScaleConfig(traffic=traffic, ha=False, multi_region=False),
        **kwargs,
    )


def test_azure_low_traffic_app_service_b1():
    tf = generate_azure(_make_azure_req_traffic("low")).terraform["main.tf"]
    assert "B1" in tf


def test_azure_medium_traffic_app_service_s1():
    tf = generate_azure(_make_azure_req_traffic("medium")).terraform["main.tf"]
    assert "S1" in tf


def test_azure_high_traffic_app_service_p1v2():
    tf = generate_azure(_make_azure_req_traffic("high")).terraform["main.tf"]
    assert "P1v2" in tf


def test_azure_traffic_sku_sizes_are_distinct():
    low  = generate_azure(_make_azure_req_traffic("low")).terraform["main.tf"]
    med  = generate_azure(_make_azure_req_traffic("medium")).terraform["main.tf"]
    high = generate_azure(_make_azure_req_traffic("high")).terraform["main.tf"]
    assert low != med
    assert med != high
