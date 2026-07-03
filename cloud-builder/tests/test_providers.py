import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import WizardRequest, ScaleConfig
from providers.aws import generate_aws


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
