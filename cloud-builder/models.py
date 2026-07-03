from typing import Literal
from pydantic import BaseModel, field_validator


class ScaleConfig(BaseModel):
    traffic: Literal["low", "medium", "high"]
    ha: bool
    multi_region: bool


class WizardRequest(BaseModel):
    provider: Literal["aws", "azure"]
    app_type: Literal["web", "api", "batch", "data_pipeline"]
    components: list[str]
    scale: ScaleConfig
    notes: str = ""

    @field_validator("components")
    @classmethod
    def validate_components(cls, v: list[str]) -> list[str]:
        allowed = {"db", "cache", "queue", "cdn", "storage"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"허용되지 않는 컴포넌트: {invalid}")
        return v


class GenerateResponse(BaseModel):
    summary: str
    diagram: str
    terraform: dict[str, str]
