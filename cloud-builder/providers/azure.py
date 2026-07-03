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


_APP_SERVICE_SKUS = {
    "low":    ("Basic",    "B1"),
    "medium": ("Standard", "S1"),
    "high":   ("PremiumV2", "P1v2"),
}


def _tf_app_service(traffic: str) -> str:
    tier, size = _APP_SERVICE_SKUS.get(traffic, ("Standard", "S1"))
    return f'''\
resource "azurerm_app_service_plan" "main" {{
  name                = "${{var.project_name}}-plan"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku {{ tier = "{tier}" size = "{size}" }}
}}

resource "azurerm_app_service" "main" {{
  name                = "${{var.project_name}}-app"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  app_service_plan_id = azurerm_app_service_plan.main.id
}}'''


def _build_terraform(req: WizardRequest) -> dict[str, str]:
    main_blocks = [_TF_BASE, _tf_app_service(req.scale.traffic)]
    if "db" in req.components:
        main_blocks.append(_TF_SQL)
    if "cache" in req.components:
        main_blocks.append(_TF_REDIS)
    if "cdn" in req.components:
        main_blocks.append(_TF_CDN)
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


_TF_CDN = '''\
resource "azurerm_cdn_profile" "main" {
  name                = "${var.project_name}-cdn"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard_Microsoft"
}

resource "azurerm_cdn_endpoint" "main" {
  name                = "${var.project_name}-endpoint"
  profile_name        = azurerm_cdn_profile.main.name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  origin {
    name      = "main-origin"
    host_name = var.cdn_origin_host_name
  }
}'''

_TF_SQL = '''\
resource "azurerm_mssql_server" "main" {
  name                         = "${var.project_name}-sql"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  version                      = "12.0"
  administrator_login          = var.sql_admin_login
  administrator_login_password = var.sql_admin_password
}

resource "azurerm_mssql_database" "main" {
  name      = var.db_name
  server_id = azurerm_mssql_server.main.id
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
variable "project_name"         { type = string }
variable "location"             { type = string  default = "koreacentral" }
variable "resource_group_name"  { type = string }
variable "vnet_cidr"            { type = string  default = "10.0.0.0/16" }
variable "subnet_cidr"          { type = string  default = "10.0.1.0/24" }
variable "sql_admin_login"      { type = string }
variable "sql_admin_password"   { type = string  sensitive = true }
variable "db_name"              { type = string  default = "appdb" }
variable "storage_account_name" { type = string  default = "" }
variable "cdn_origin_host_name" { type = string  default = "" }'''

_TF_OUTPUTS = '''\
output "resource_group_id" { value = azurerm_resource_group.main.id }
output "vnet_id"           { value = azurerm_virtual_network.main.id }'''
