# The Azure resources of guidesSystem, as created by infra/setup.sh on 19 Nov 2026 and taken over with imports.tf.
# Deliberately not managed here (see ADR-8):
# - the two databases: the SQL free offer has no setting in the azurerm provider, so they stay in infra/setup.sh;
# - the containers' image, environment variables and secrets: CD changes them on every deploy;
# - the role assignments: created once by infra/setup.sh.

variable "sql_admin_password" {
  type        = string
  sensitive   = true
  description = "SQL server admin password, typed in at plan time (TF_VAR_sql_admin_password); never stored in the state"
}

locals {
  prefix   = "oespineira-ieu2024"
  location = "swedencentral"
}

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.prefix}"
  location = local.location
}

# The UI: a storage static website
resource "azurerm_storage_account" "ui" {
  #checkov:skip=CKV_AZURE_59:A public static website by design (A2 deployment guide, step 3)
  #checkov:skip=CKV2_AZURE_33:A public website cannot sit behind a private endpoint; private endpoints are outside the allowance
  #checkov:skip=CKV_AZURE_206:LRS as the guide specifies; the UI is re-uploaded by CD on every deploy, geo-replication would only add cost
  #checkov:skip=CKV_AZURE_33:The queue service is not used
  #checkov:skip=CKV2_AZURE_40:CD uploads the UI with the account key; replacing it needs a data-plane role for the pipeline (future improvement)
  #checkov:skip=CKV2_AZURE_1:Encrypted at rest with Microsoft-managed keys; a customer-managed key needs a Key Vault, outside the allowance
  name                            = "oespineiraieu2024ui"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = local.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false
  # CD uploads the UI with the account key (see the CKV2_AZURE_40 skip), so shared keys stay on,
  # and the SAS expiration policy below limits any shared-access link to one day.
  shared_access_key_enabled = true

  # Checkov CKV2_AZURE_38: deleted UI files can be recovered for 7 days
  blob_properties {
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }

  # Checkov CKV2_AZURE_41: any shared-access link expires within a day
  sas_policy {
    expiration_period = "01.00:00:00"
    expiration_action = "Log"
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "azurerm_storage_account_static_website" "ui" {
  storage_account_id = azurerm_storage_account.ui.id
  index_document     = "index.html"
}

# The SQL server (its two databases are created by infra/setup.sh, see above)
resource "azurerm_mssql_server" "main" {
  #checkov:skip=CKV_AZURE_113:Consumption Container Apps reach the database over its public endpoint; a private one needs a VNet, outside the allowance
  #checkov:skip=CKV2_AZURE_45:Same reason: private endpoints are outside the allowance
  #checkov:skip=CKV2_AZURE_27:The guide specifies contained SQL users; managed-identity login would remove the passwords (future improvement)
  #checkov:skip=CKV_AZURE_23:Auditing needs a storage account or Log Analytics as destination, outside the allowance
  #checkov:skip=CKV_AZURE_24:No auditing, so no audit retention (see CKV_AZURE_23)
  #checkov:skip=CKV2_AZURE_2:Vulnerability assessment needs Microsoft Defender for SQL (paid) and a storage account
  name                = "${local.prefix}-sql"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
  version             = "12.0"
  administrator_login = "sqladmin"
  # Write-only: Terraform sends the password but never saves it in its state file.
  administrator_login_password_wo         = var.sql_admin_password
  administrator_login_password_wo_version = 1
  minimum_tls_version                     = "1.2"

  lifecycle {
    prevent_destroy = true
    # The password was set by infra/setup.sh; Terraform only sends it again if the version number changes.
    ignore_changes = [administrator_login_password_wo_version]
  }
}

# 0.0.0.0 is Azure's way of saying "allow Azure services" (the Container Apps)
resource "azurerm_mssql_firewall_rule" "azure_services" {
  #checkov:skip=CKV2_AZURE_34:"Allow Azure services" is required by the A2 deployment guide so the Container Apps can connect; limitation recorded in ADR-8
  name             = "AllowAzureServices"
  server_id        = azurerm_mssql_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}


# The containers' logs (part of the allowance since the 28 Nov update of section 7).
# Daily cap of 0.15 GB, about 4.5 GB a month: under the free 5 GB, so it cannot use the credit.
resource "azurerm_log_analytics_workspace" "logs" {
  name                = "${local.prefix}-logs"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  daily_quota_gb      = 0.15

  lifecycle {
    prevent_destroy = true
  }
}

# Container Apps: the environment, then one app per service
resource "azurerm_container_app_environment" "main" {
  name                       = "${local.prefix}-env"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = local.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.logs.id


  # Pay per use: no dedicated workload profiles
  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_app" "kraal" {
  name                         = "${local.prefix}-kraal"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1
    # Created by Azure with the app: one more replica per 10 concurrent requests (capped by max_replicas)
    http_scale_rule {
      name                = "http-scaler"
      concurrent_requests = "10"
    }
    container {
      name   = "${local.prefix}-kraal"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  lifecycle {
    prevent_destroy = true
    # CD owns the image, the environment variables and the secrets. Azure does not report the traffic split
    # in single-revision mode, and leaves the scaling timings at its own defaults.
    ignore_changes = [
      template[0].container[0].image,
      template[0].container[0].env,
      secret,
      ingress[0].traffic_weight,
      template[0].cooldown_period_in_seconds,
      template[0].polling_interval_in_seconds,
    ]
  }
}

resource "azurerm_container_app" "actas" {
  name                         = "${local.prefix}-actas"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"

  ingress {
    external_enabled = true
    target_port      = 8000
    transport        = "http"
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1
    # Created by Azure with the app: one more replica per 10 concurrent requests (capped by max_replicas)
    http_scale_rule {
      name                = "http-scaler"
      concurrent_requests = "10"
    }
    container {
      name   = "${local.prefix}-actas"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      cpu    = 0.25
      memory = "0.5Gi"
    }
  }

  lifecycle {
    prevent_destroy = true
    # CD owns the image, the environment variables and the secrets. Azure does not report the traffic split
    # in single-revision mode, and leaves the scaling timings at its own defaults.
    ignore_changes = [
      template[0].container[0].image,
      template[0].container[0].env,
      secret,
      ingress[0].traffic_weight,
      template[0].cooldown_period_in_seconds,
      template[0].polling_interval_in_seconds,
    ]
  }
}

# The pipeline's identity: Contributor on the resource group (assigned by infra/setup.sh), trusted through OIDC
resource "azurerm_user_assigned_identity" "github" {
  name                = "${local.prefix}-github"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
}

resource "azurerm_federated_identity_credential" "github_main" {
  name                      = "github-main"
  user_assigned_identity_id = azurerm_user_assigned_identity.github.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:oliespineira/guidesSystem:ref:refs/heads/main"
}

resource "azurerm_federated_identity_credential" "github_main_ids" {
  name                      = "github-main-ids"
  user_assigned_identity_id = azurerm_user_assigned_identity.github.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:oliespineira@184248689/guidesSystem@1370236958:ref:refs/heads/main"
}