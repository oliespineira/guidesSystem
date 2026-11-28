# Each block says: this resource in the code IS this existing resource in Azure.
# The databases are deliberately not here: see ADR-8 (the SQL free offer is created by infra/setup.sh).
locals {
  rg_id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-oespineira-ieu2024"
}

variable "subscription_id" {
  type        = string
  description = "Azure for Students subscription ID (not a secret, but kept out of the code)"
}

import {
  to = azurerm_resource_group.main
  id = local.rg_id
}

import {
  to = azurerm_storage_account.ui
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/oespineiraieu2024ui"
}

import {
  to = azurerm_mssql_server.main
  id = "${local.rg_id}/providers/Microsoft.Sql/servers/oespineira-ieu2024-sql"
}

import {
  to = azurerm_mssql_firewall_rule.azure_services
  id = "${local.rg_id}/providers/Microsoft.Sql/servers/oespineira-ieu2024-sql/firewallRules/AllowAzureServices"
}

import {
  to = azurerm_container_app_environment.main
  id = "${local.rg_id}/providers/Microsoft.App/managedEnvironments/oespineira-ieu2024-env"
}

import {
  to = azurerm_container_app.kraal
  id = "${local.rg_id}/providers/Microsoft.App/containerApps/oespineira-ieu2024-kraal"
}

import {
  to = azurerm_container_app.actas
  id = "${local.rg_id}/providers/Microsoft.App/containerApps/oespineira-ieu2024-actas"
}

import {
  to = azurerm_user_assigned_identity.github
  id = "${local.rg_id}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/oespineira-ieu2024-github"
}

import {
  to = azurerm_federated_identity_credential.github_main
  id = "${local.rg_id}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/oespineira-ieu2024-github/federatedIdentityCredentials/github-main"
}

import {
  to = azurerm_federated_identity_credential.github_main_ids
  id = "${local.rg_id}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/oespineira-ieu2024-github/federatedIdentityCredentials/github-main-ids"
}
import {
  to = azurerm_storage_account_static_website.ui
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/oespineiraieu2024ui"
}

import {
  to = azurerm_log_analytics_workspace.logs
  id = "${local.rg_id}/providers/Microsoft.OperationalInsights/workspaces/oespineira-ieu2024-logs"
}