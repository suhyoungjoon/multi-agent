# Cloud Project Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 브라우저 wizard를 통해 프로젝트 요구사항을 입력받아 AWS/Azure 아키텍처 설명·Mermaid 다이어그램·Terraform 템플릿을 생성하는 웹 도구를 구축한다.

**Architecture:** FastAPI 백엔드가 `/generate` 엔드포인트로 wizard 입력을 받아 provider 모듈(aws.py/azure.py)에서 결과를 생성한다. 프론트엔드는 바닐라 JS + Mermaid.js CDN으로 구성되며 FastAPI가 정적 파일을 서빙한다.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pydantic, pytest, httpx (테스트용), 바닐라 JS, Mermaid.js (CDN)

## Global Constraints

- Python 표준 라이브러리 + fastapi + uvicorn + pydantic + pytest + httpx 만 사용 (서드파티 최소화)
- 모든 새 파일은 `cloud-builder/` 디렉터리 아래에 생성
- Terraform 템플릿은 실제 값 없이 variable 블록으로만 구성
- TDD: 테스트 먼저 작성 후 구현
- 커밋은 태스크 단위로

---

## File Map

| 파일 | 역할 |
|------|------|
| `cloud-builder/main.py` | FastAPI 앱, 라우터 등록, 정적파일 마운트 |
| `cloud-builder/models.py` | Pydantic 요청/응답 모델 |
| `cloud-builder/wizard/steps.py` | wizard 5단계 메타데이터 (질문·선택지 정의) |
| `cloud-builder/providers/aws.py` | AWS 텍스트·다이어그램·Terraform 생성 함수 |
| `cloud-builder/providers/azure.py` | Azure 텍스트·다이어그램·Terraform 생성 함수 |
| `cloud-builder/static/index.html` | Wizard + 결과 UI |
| `cloud-builder/static/app.js` | 단계 진행, API 호출, Mermaid 렌더링 |
| `cloud-builder/tests/test_providers.py` | provider 단위 테스트 |
| `cloud-builder/tests/test_api.py` | API 통합 테스트 |

---

## Task 1: 프로젝트 스캐폴딩 + 모델 정의

**Files:**
- Create: `cloud-builder/__init__.py`
- Create: `cloud-builder/models.py`
- Create: `cloud-builder/wizard/__init__.py`
- Create: `cloud-builder/providers/__init__.py`
- Create: `cloud-builder/static/` (빈 디렉터리)
- Create: `cloud-builder/tests/__init__.py`
- Create: `cloud-builder/requirements.txt`

**Interfaces:**
- Produces: `WizardRequest`, `ScaleConfig`, `GenerateResponse` Pydantic 모델

- [ ] **Step 1: 디렉터리 생성**

```bash
mkdir -p cloud-builder/wizard cloud-builder/providers cloud-builder/static cloud-builder/tests
touch cloud-builder/__init__.py cloud-builder/wizard/__init__.py cloud-builder/providers/__init__.py cloud-builder/tests/__init__.py
```

- [ ] **Step 2: requirements.txt 작성**

`cloud-builder/requirements.txt`:
```
fastapi>=0.110.0
uvicorn>=0.29.0
pydantic>=2.6.0
httpx>=0.27.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 3: 테스트 작성 (모델 유효성)**

`cloud-builder/tests/test_models.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 → FAIL 확인**

```bash
cd cloud-builder && python -m pytest tests/test_models.py -v
```
Expected: ImportError (models.py 없음)

- [ ] **Step 5: models.py 구현**

`cloud-builder/models.py`:
```python
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
```

- [ ] **Step 6: 테스트 실행 → PASS 확인**

```bash
cd cloud-builder && python -m pytest tests/test_models.py -v
```
Expected: 3 passed

- [ ] **Step 7: 커밋**

```bash
git add cloud-builder/
git commit -m "feat: cloud-builder 스캐폴딩 + Pydantic 모델"
```

---

## Task 2: AWS Provider

**Files:**
- Create: `cloud-builder/providers/aws.py`
- Test: `cloud-builder/tests/test_providers.py`

**Interfaces:**
- Consumes: `WizardRequest` (from `models.py`)
- Produces:
  - `generate_aws(req: WizardRequest) -> GenerateResponse`

- [ ] **Step 1: 테스트 작성**

`cloud-builder/tests/test_providers.py`:
```python
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
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
cd cloud-builder && python -m pytest tests/test_providers.py -v
```
Expected: ImportError

- [ ] **Step 3: aws.py 구현**

`cloud-builder/providers/aws.py`:
```python
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
    main_blocks = [_TF_VPC]
    if "db" in req.components:
        main_blocks.append(_TF_RDS)
    if "cache" in req.components:
        main_blocks.append(_TF_ELASTICACHE)
    if "cdn" in req.components:
        main_blocks.append(_TF_CLOUDFRONT)
    if "queue" in req.components:
        main_blocks.append(_TF_SQS)
    if "storage" in req.components:
        main_blocks.append(_TF_S3)
    return {
        "main.tf": "\n\n".join(main_blocks),
        "variables.tf": _TF_VARIABLES,
        "outputs.tf": _TF_OUTPUTS,
    }

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

_TF_RDS = '''\
resource "aws_db_instance" "main" {
  engine         = var.db_engine
  instance_class = var.db_instance_class
  username       = var.db_username
  password       = var.db_password
  skip_final_snapshot = true
}'''

_TF_ELASTICACHE = '''\
resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${var.project_name}-cache"
  engine               = "redis"
  node_type            = var.cache_node_type
  num_cache_nodes      = 1
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
variable "project_name"        { type = string }
variable "aws_region"          { type = string  default = "ap-northeast-2" }
variable "vpc_cidr"            { type = string  default = "10.0.0.0/16" }
variable "public_subnet_cidr"  { type = string  default = "10.0.1.0/24" }
variable "db_engine"           { type = string  default = "postgres" }
variable "db_instance_class"   { type = string  default = "db.t3.micro" }
variable "db_username"         { type = string }
variable "db_password"         { type = string  sensitive = true }
variable "cache_node_type"     { type = string  default = "cache.t3.micro" }
variable "origin_domain"       { type = string  default = "" }
variable "s3_bucket_name"      { type = string  default = "" }'''

_TF_OUTPUTS = '''\
output "vpc_id"    { value = aws_vpc.main.id }
output "subnet_id" { value = aws_subnet.public.id }'''
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
cd cloud-builder && python -m pytest tests/test_providers.py -v
```
Expected: 7 passed

- [ ] **Step 5: 커밋**

```bash
git add cloud-builder/providers/aws.py cloud-builder/tests/test_providers.py
git commit -m "feat: AWS provider — 아키텍처·다이어그램·Terraform 생성"
```

---

## Task 3: Azure Provider

**Files:**
- Modify: `cloud-builder/tests/test_providers.py` (Azure 테스트 추가)
- Create: `cloud-builder/providers/azure.py`

**Interfaces:**
- Consumes: `WizardRequest` (from `models.py`)
- Produces: `generate_azure(req: WizardRequest) -> GenerateResponse`

- [ ] **Step 1: Azure 테스트 추가 (test_providers.py 하단에 추가)**

```python
from providers.azure import generate_azure

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
    assert "azurerm_sql_server" in resp.terraform["main.tf"]

def test_azure_cache_adds_redis():
    resp = generate_azure(_make_azure_req(components=["cache"]))
    assert "azurerm_redis_cache" in resp.terraform["main.tf"]

def test_azure_storage_adds_account():
    resp = generate_azure(_make_azure_req(components=["storage"]))
    assert "azurerm_storage_account" in resp.terraform["main.tf"]
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
cd cloud-builder && python -m pytest tests/test_providers.py -k azure -v
```
Expected: ImportError

- [ ] **Step 3: azure.py 구현**

`cloud-builder/providers/azure.py`:
```python
from models import WizardRequest, GenerateResponse

def generate_azure(req: WizardRequest) -> GenerateResponse:
    return GenerateResponse(
        summary=_build_summary(req),
        diagram=_build_diagram(req),
        terraform=_build_terraform(req),
    )

def _build_summary(req: WizardRequest) -> str:
    comp_names = {"db": "Azure SQL", "cache": "Azure Cache for Redis",
                  "cdn": "Azure CDN", "queue": "Service Bus", "storage": "Storage Account"}
    comps = ", ".join(comp_names.get(c, c) for c in req.components) or "없음"
    ha_text = "가용성 집합(Availability Set)" if req.scale.ha else "단일 인스턴스"
    return (
        f"Azure 기반 {req.app_type} 아키텍처입니다. "
        f"사용 컴포넌트: {comps}. "
        f"트래픽 규모: {req.scale.traffic}. "
        f"가용성: {ha_text}. "
        f"Resource Group + VNet + Subnet으로 네트워크를 구성하고, "
        f"App Service 또는 VM으로 애플리케이션을 서빙합니다."
    )

def _build_diagram(req: WizardRequest) -> str:
    lines = ["graph TD", "  Internet([Internet]) --> LB[Azure Load Balancer]",
             "  LB --> App[App Service / VM]", "  App --> VNet[VNet + Subnet]"]
    if "db" in req.components:
        lines.append("  App --> SQL[(Azure SQL)]")
    if "cache" in req.components:
        lines.append("  App --> Redis[(Azure Cache for Redis)]")
    if "cdn" in req.components:
        lines.insert(1, "  Internet --> CDN[Azure CDN]")
    if "queue" in req.components:
        lines.append("  App --> Bus[Service Bus]")
    if "storage" in req.components:
        lines.append("  App --> Storage[(Storage Account)]")
    return "\n".join(lines)

def _build_terraform(req: WizardRequest) -> dict[str, str]:
    main_blocks = [_TF_BASE]
    if "db" in req.components:
        main_blocks.append(_TF_SQL)
    if "cache" in req.components:
        main_blocks.append(_TF_REDIS)
    if "storage" in req.components:
        main_blocks.append(_TF_STORAGE)
    if "queue" in req.components:
        main_blocks.append(_TF_SERVICEBUS)
    return {
        "main.tf": "\n\n".join(main_blocks),
        "variables.tf": _TF_VARIABLES,
        "outputs.tf": _TF_OUTPUTS,
    }

_TF_BASE = '''\
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_virtual_network" "main" {
  name                = "${var.project_name}-vnet"
  address_space       = [var.vnet_cidr]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "main" {
  name                 = "default"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = [var.subnet_cidr]
}'''

_TF_SQL = '''\
resource "azurerm_sql_server" "main" {
  name                         = "${var.project_name}-sql"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0"
  administrator_login          = var.sql_admin_login
  administrator_login_password = var.sql_admin_password
}

resource "azurerm_sql_database" "main" {
  name                = var.db_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  server_name         = azurerm_sql_server.main.name
}'''

_TF_REDIS = '''\
resource "azurerm_redis_cache" "main" {
  name                = "${var.project_name}-redis"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  capacity            = 1
  family              = "C"
  sku_name            = "Basic"
}'''

_TF_STORAGE = '''\
resource "azurerm_storage_account" "main" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}'''

_TF_SERVICEBUS = '''\
resource "azurerm_servicebus_namespace" "main" {
  name                = "${var.project_name}-bus"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard"
}'''

_TF_VARIABLES = '''\
variable "project_name"          { type = string }
variable "location"              { type = string  default = "koreacentral" }
variable "resource_group_name"   { type = string }
variable "vnet_cidr"             { type = string  default = "10.0.0.0/16" }
variable "subnet_cidr"           { type = string  default = "10.0.1.0/24" }
variable "sql_admin_login"       { type = string }
variable "sql_admin_password"    { type = string  sensitive = true }
variable "db_name"               { type = string  default = "appdb" }
variable "storage_account_name"  { type = string  default = "" }'''

_TF_OUTPUTS = '''\
output "resource_group_id" { value = azurerm_resource_group.main.id }
output "vnet_id"           { value = azurerm_virtual_network.main.id }'''
```

- [ ] **Step 4: 테스트 실행 → PASS 확인**

```bash
cd cloud-builder && python -m pytest tests/test_providers.py -v
```
Expected: 13 passed

- [ ] **Step 5: 커밋**

```bash
git add cloud-builder/providers/azure.py cloud-builder/tests/test_providers.py
git commit -m "feat: Azure provider — 아키텍처·다이어그램·Terraform 생성"
```

---

## Task 4: FastAPI 앱 + API 엔드포인트

**Files:**
- Create: `cloud-builder/main.py`
- Create: `cloud-builder/tests/test_api.py`

**Interfaces:**
- Consumes: `generate_aws(req)`, `generate_azure(req)`, `WizardRequest`, `GenerateResponse`
- Produces:
  - `GET /` → `index.html` (정적 파일 서빙)
  - `POST /generate` → `GenerateResponse` JSON
  - `GET /download/terraform?provider=aws` → zip 파일 (BytesIO)

- [ ] **Step 1: API 테스트 작성**

`cloud-builder/tests/test_api.py`:
```python
import pytest
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_generate_aws():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/generate", json={
            "provider": "aws", "app_type": "web",
            "components": ["db"],
            "scale": {"traffic": "medium", "ha": True, "multi_region": False},
        })
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert body["diagram"].startswith("graph TD")
    assert "main.tf" in body["terraform"]

@pytest.mark.asyncio
async def test_generate_azure():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/generate", json={
            "provider": "azure", "app_type": "api",
            "components": ["cache"],
            "scale": {"traffic": "low", "ha": False, "multi_region": False},
        })
    assert resp.status_code == 200
    assert "Azure" in resp.json()["summary"]

@pytest.mark.asyncio
async def test_generate_invalid_provider():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/generate", json={
            "provider": "gcp", "app_type": "web",
            "components": [],
            "scale": {"traffic": "low", "ha": False, "multi_region": False},
        })
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_download_terraform_returns_zip():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        gen = await c.post("/generate", json={
            "provider": "aws", "app_type": "web", "components": [],
            "scale": {"traffic": "low", "ha": False, "multi_region": False},
        })
        resp = await c.get(f"/download/terraform", params={
            "provider": "aws", "app_type": "web", "components": [],
            "traffic": "low", "ha": "false", "multi_region": "false",
        })
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

```bash
cd cloud-builder && python -m pytest tests/test_api.py -v
```
Expected: ImportError (main.py 없음)

- [ ] **Step 3: main.py 구현**

`cloud-builder/main.py`:
```python
import io
import zipfile
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from models import WizardRequest, GenerateResponse
from providers.aws import generate_aws
from providers.azure import generate_azure

app = FastAPI(title="Cloud Project Builder")

@app.post("/generate", response_model=GenerateResponse)
def generate(req: WizardRequest) -> GenerateResponse:
    if req.provider == "aws":
        return generate_aws(req)
    return generate_azure(req)

@app.get("/download/terraform")
def download_terraform(
    provider: str = Query(...),
    app_type: str = Query(...),
    components: list[str] = Query(default=[]),
    traffic: str = Query("medium"),
    ha: bool = Query(False),
    multi_region: bool = Query(False),
):
    from models import ScaleConfig
    req = WizardRequest(
        provider=provider, app_type=app_type, components=components,
        scale=ScaleConfig(traffic=traffic, ha=ha, multi_region=multi_region),
    )
    result = generate_aws(req) if provider == "aws" else generate_azure(req)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for fname, content in result.terraform.items():
            zf.writestr(fname, content)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=terraform.zip"},
    )

app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

- [ ] **Step 4: pytest.ini 작성 (asyncio 모드 설정)**

`cloud-builder/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 5: 테스트 실행 → PASS 확인**

```bash
cd cloud-builder && pip install -r requirements.txt -q && python -m pytest tests/test_api.py -v
```
Expected: 4 passed

- [ ] **Step 6: 커밋**

```bash
git add cloud-builder/main.py cloud-builder/tests/test_api.py cloud-builder/pytest.ini
git commit -m "feat: FastAPI 앱 — /generate + /download/terraform 엔드포인트"
```

---

## Task 5: 웹 UI (Wizard + 결과 화면)

**Files:**
- Create: `cloud-builder/static/index.html`
- Create: `cloud-builder/static/app.js`

**Interfaces:**
- Consumes: `POST /generate` API (Task 4)

- [ ] **Step 1: index.html 작성**

`cloud-builder/static/index.html`:
```html
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cloud Project Builder</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: #f5f7fa; color: #222; }
  .container { max-width: 720px; margin: 40px auto; padding: 0 16px; }
  h1 { font-size: 1.6rem; margin-bottom: 24px; }
  .card { background: #fff; border-radius: 10px; padding: 28px;
          box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 16px; }
  .step-indicator { display: flex; gap: 8px; margin-bottom: 24px; }
  .step-dot { width: 10px; height: 10px; border-radius: 50%; background: #ddd; }
  .step-dot.active { background: #4f6ef7; }
  .step-dot.done { background: #34c759; }
  h2 { font-size: 1.1rem; margin-bottom: 16px; }
  .options { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
  .opt-btn { padding: 10px 18px; border: 2px solid #e0e0e0; border-radius: 8px;
             background: #fff; cursor: pointer; font-size: 0.95rem; transition: all .15s; }
  .opt-btn.selected { border-color: #4f6ef7; background: #eef1ff; color: #4f6ef7; }
  .opt-btn:hover { border-color: #4f6ef7; }
  .check-group { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
  .check-item { display: flex; align-items: center; gap: 6px; cursor: pointer; }
  textarea { width: 100%; height: 80px; border: 1px solid #ddd; border-radius: 6px;
             padding: 8px; font-size: 0.9rem; resize: vertical; margin-bottom: 20px; }
  .nav { display: flex; justify-content: space-between; }
  .btn { padding: 10px 24px; border: none; border-radius: 8px; cursor: pointer;
         font-size: 0.95rem; font-weight: 600; }
  .btn-primary { background: #4f6ef7; color: #fff; }
  .btn-secondary { background: #eee; color: #444; }
  .btn:disabled { opacity: .4; cursor: not-allowed; }
  .tabs { display: flex; gap: 0; border-bottom: 2px solid #eee; margin-bottom: 20px; }
  .tab { padding: 10px 20px; cursor: pointer; border-bottom: 2px solid transparent;
         margin-bottom: -2px; font-weight: 500; }
  .tab.active { border-bottom-color: #4f6ef7; color: #4f6ef7; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  pre { background: #1e1e2e; color: #cdd6f4; padding: 16px; border-radius: 8px;
        overflow-x: auto; font-size: 0.85rem; line-height: 1.5; }
  .copy-btn { float: right; padding: 4px 12px; background: #4f6ef7; color: #fff;
              border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem; margin-bottom: 8px; }
  .dl-btn { display: inline-block; margin-top: 12px; padding: 8px 16px;
            background: #34c759; color: #fff; border: none; border-radius: 6px;
            cursor: pointer; font-size: 0.9rem; }
  #loading { text-align: center; padding: 40px; color: #666; }
  .hidden { display: none !important; }
  .range-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
  .range-row label { min-width: 100px; }
  input[type=range] { flex: 1; }
  .range-val { min-width: 60px; color: #4f6ef7; font-weight: 600; }
</style>
</head>
<body>
<div class="container">
  <h1>Cloud Project Builder</h1>
  <div id="wizard-section" class="card">
    <div class="step-indicator" id="step-dots"></div>
    <div id="step-container"></div>
  </div>
  <div id="loading" class="hidden">아키텍처 생성 중...</div>
  <div id="result-section" class="hidden card">
    <h2>생성된 아키텍처</h2>
    <div class="tabs">
      <div class="tab active" data-tab="summary">설명</div>
      <div class="tab" data-tab="diagram">다이어그램</div>
      <div class="tab" data-tab="terraform">Terraform</div>
    </div>
    <div id="tab-summary" class="tab-content active"></div>
    <div id="tab-diagram" class="tab-content"><div id="mermaid-container"></div></div>
    <div id="tab-terraform" class="tab-content">
      <div id="tf-files"></div>
      <button class="dl-btn" id="dl-btn">Terraform 다운로드 (.zip)</button>
    </div>
  </div>
</div>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: app.js 작성**

`cloud-builder/static/app.js`:
```javascript
mermaid.initialize({ startOnLoad: false, theme: "default" });

const STEPS = [
  {
    id: "provider", title: "클라우드 제공자를 선택하세요",
    type: "single",
    options: [{ value: "aws", label: "AWS" }, { value: "azure", label: "Azure" }],
  },
  {
    id: "app_type", title: "애플리케이션 유형을 선택하세요",
    type: "single",
    options: [
      { value: "web", label: "웹앱" }, { value: "api", label: "API 서버" },
      { value: "batch", label: "배치" }, { value: "data_pipeline", label: "데이터 파이프라인" },
    ],
  },
  {
    id: "components", title: "사용할 컴포넌트를 선택하세요 (복수 선택 가능)",
    type: "multi",
    options: [
      { value: "db", label: "데이터베이스" }, { value: "cache", label: "캐시" },
      { value: "queue", label: "메시지 큐" }, { value: "cdn", label: "CDN" },
      { value: "storage", label: "스토리지" },
    ],
  },
  {
    id: "scale", title: "규모와 요구사항을 설정하세요",
    type: "scale",
  },
  {
    id: "notes", title: "추가 요구사항이 있으면 입력하세요 (선택)",
    type: "text",
  },
];

let state = { provider: null, app_type: null, components: [], scale: { traffic: "medium", ha: false, multi_region: false }, notes: "" };
let currentStep = 0;
let lastResult = null;

function renderDots() {
  const el = document.getElementById("step-dots");
  el.innerHTML = STEPS.map((_, i) =>
    `<div class="step-dot ${i < currentStep ? "done" : i === currentStep ? "active" : ""}"></div>`
  ).join("");
}

function renderStep() {
  renderDots();
  const step = STEPS[currentStep];
  const c = document.getElementById("step-container");
  if (step.type === "single") {
    c.innerHTML = `<h2>${step.title}</h2><div class="options">${
      step.options.map(o => `<button class="opt-btn${state[step.id]===o.value?" selected":""}" data-val="${o.value}">${o.label}</button>`).join("")
    }</div><div class="nav"><button class="btn btn-secondary" id="btn-back" ${currentStep===0?"disabled":""}>이전</button>
    <button class="btn btn-primary" id="btn-next" ${!state[step.id]?"disabled":""}>다음</button></div>`;
    c.querySelectorAll(".opt-btn").forEach(b => b.addEventListener("click", () => {
      state[step.id] = b.dataset.val;
      renderStep();
    }));
  } else if (step.type === "multi") {
    c.innerHTML = `<h2>${step.title}</h2><div class="check-group">${
      step.options.map(o => `<label class="check-item"><input type="checkbox" value="${o.value}" ${state.components.includes(o.value)?"checked":""}> ${o.label}</label>`).join("")
    }</div><div class="nav"><button class="btn btn-secondary" id="btn-back">이전</button>
    <button class="btn btn-primary" id="btn-next">다음</button></div>`;
    c.querySelectorAll("input[type=checkbox]").forEach(cb => cb.addEventListener("change", () => {
      state.components = [...c.querySelectorAll("input:checked")].map(x => x.value);
    }));
  } else if (step.type === "scale") {
    const tv = { low: "낮음", medium: "보통", high: "높음" };
    c.innerHTML = `<h2>${step.title}</h2>
    <div class="range-row"><label>예상 트래픽</label><input type="range" min="0" max="2" value="${["low","medium","high"].indexOf(state.scale.traffic)}" id="traffic-slider"><span class="range-val" id="traffic-val">${tv[state.scale.traffic]}</span></div>
    <div class="check-group">
      <label class="check-item"><input type="checkbox" id="ha-check" ${state.scale.ha?"checked":""}> 고가용성(HA) 필요</label>
      <label class="check-item"><input type="checkbox" id="mr-check" ${state.scale.multi_region?"checked":""}> 멀티 리전</label>
    </div>
    <div class="nav"><button class="btn btn-secondary" id="btn-back">이전</button><button class="btn btn-primary" id="btn-next">다음</button></div>`;
    const levels = ["low", "medium", "high"];
    c.querySelector("#traffic-slider").addEventListener("input", e => {
      state.scale.traffic = levels[e.target.value];
      c.querySelector("#traffic-val").textContent = tv[state.scale.traffic];
    });
    c.querySelector("#ha-check").addEventListener("change", e => state.scale.ha = e.target.checked);
    c.querySelector("#mr-check").addEventListener("change", e => state.scale.multi_region = e.target.checked);
  } else if (step.type === "text") {
    c.innerHTML = `<h2>${step.title}</h2>
    <textarea placeholder="예: 한국어 지원 필요, 특정 리전 고정 등">${state.notes}</textarea>
    <div class="nav"><button class="btn btn-secondary" id="btn-back">이전</button>
    <button class="btn btn-primary" id="btn-generate">아키텍처 생성</button></div>`;
    c.querySelector("textarea").addEventListener("input", e => state.notes = e.target.value);
    c.querySelector("#btn-generate").addEventListener("click", generate);
  }
  const backBtn = c.querySelector("#btn-back");
  if (backBtn) backBtn.addEventListener("click", () => { currentStep--; renderStep(); });
  const nextBtn = c.querySelector("#btn-next");
  if (nextBtn) nextBtn.addEventListener("click", () => { currentStep++; renderStep(); });
}

async function generate() {
  document.getElementById("wizard-section").classList.add("hidden");
  document.getElementById("loading").classList.remove("hidden");
  const resp = await fetch("/generate", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state),
  });
  lastResult = await resp.json();
  document.getElementById("loading").classList.add("hidden");
  renderResult(lastResult);
}

function renderResult(data) {
  const sec = document.getElementById("result-section");
  sec.classList.remove("hidden");
  document.getElementById("tab-summary").innerHTML = `<p style="line-height:1.7">${data.summary}</p>`;
  const mc = document.getElementById("mermaid-container");
  mc.innerHTML = `<div class="mermaid">${data.diagram}</div>`;
  mermaid.run({ nodes: mc.querySelectorAll(".mermaid") });
  const tfEl = document.getElementById("tf-files");
  tfEl.innerHTML = Object.entries(data.terraform).map(([name, code]) =>
    `<h3 style="margin:16px 0 8px">${name}</h3>
     <button class="copy-btn" onclick="navigator.clipboard.writeText(${JSON.stringify(code)})">복사</button>
     <pre><code>${code.replace(/</g,"&lt;")}</code></pre>`
  ).join("");
  document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    document.getElementById("tab-" + t.dataset.tab).classList.add("active");
  }));
  document.getElementById("dl-btn").onclick = () => {
    const params = new URLSearchParams({
      provider: state.provider, app_type: state.app_type,
      traffic: state.scale.traffic, ha: state.scale.ha, multi_region: state.scale.multi_region,
    });
    state.components.forEach(c => params.append("components", c));
    window.location.href = `/download/terraform?${params}`;
  };
}

renderStep();
```

- [ ] **Step 3: 서버 실행 후 브라우저에서 수동 확인**

```bash
cd cloud-builder && uvicorn main:app --reload --port 8000
```
브라우저에서 `http://localhost:8000` 접속 → 5단계 wizard 진행 → 결과 탭 3개 확인.

- [ ] **Step 4: 커밋**

```bash
git add cloud-builder/static/
git commit -m "feat: Wizard 웹 UI — 5단계 마법사 + 결과 탭(설명/다이어그램/Terraform)"
```

---

## Task 6: 전체 테스트 실행 + wizard/steps.py 정리

**Files:**
- Create: `cloud-builder/wizard/steps.py`

**Interfaces:**
- Produces: `STEPS: list[dict]` — 프론트에서 import 없이 사용하지만, 백엔드 테스트에서 단계 수 검증에 활용 가능

- [ ] **Step 1: wizard/steps.py 작성 (단계 메타데이터 Python 사본)**

`cloud-builder/wizard/steps.py`:
```python
STEPS = [
    {"id": "provider",    "type": "single", "title": "클라우드 제공자"},
    {"id": "app_type",    "type": "single", "title": "애플리케이션 유형"},
    {"id": "components",  "type": "multi",  "title": "컴포넌트 선택"},
    {"id": "scale",       "type": "scale",  "title": "규모/요구사항"},
    {"id": "notes",       "type": "text",   "title": "추가 요구사항"},
]
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
cd cloud-builder && python -m pytest -v
```
Expected: 모든 테스트 PASS (models 3 + providers 13 + api 4 = 20개)

- [ ] **Step 3: 최종 커밋**

```bash
git add cloud-builder/wizard/steps.py
git commit -m "feat: cloud-builder 완성 — wizard/steps.py 정리 + 전체 테스트 통과"
```
