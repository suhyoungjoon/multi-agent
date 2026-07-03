import pytest
from pydantic import ValidationError
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import WizardRequest, ScaleConfig, GenerateResponse

def test_wizard_request_valid():
    req = WizardRequest(
        provider="aws",
        app_type="web",
        components=["db", "cache"],
        scale=ScaleConfig(traffic="medium", ha=True, multi_region=False),
        notes="test",
    )
    assert req.provider == "aws"

def test_wizard_request_invalid_provider():
    with pytest.raises(ValidationError):
        WizardRequest(
            provider="gcp",
            app_type="web",
            components=[],
            scale=ScaleConfig(traffic="low", ha=False, multi_region=False),
        )

def test_generate_response_fields():
    resp = GenerateResponse(
        summary="설명",
        diagram="graph TD\n  A-->B",
        terraform={"main.tf": "resource ..."},
    )
    assert "main.tf" in resp.terraform
