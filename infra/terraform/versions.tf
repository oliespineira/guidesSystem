# Terraform describes the Azure resources that already exist (created by infra/setup.sh on 19 Nov 2026),
# and takes them over with import blocks instead of recreating them.
terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.15"
    }
  }
}

provider "azurerm" {
  features {}
  # The providers this system uses are registered once by infra/setup.sh (step 2),
  # so Terraform must not try to register every Azure service itself.
  resource_provider_registrations = "none"
  # The subscription comes from the ARM_SUBSCRIPTION_ID environment variable, never from this file.
}