resource "azurerm_resource_group" "main" {
  count = var.create_resource_group ? 1 : 0

  location = var.location
  name     = coalesce(var.resource_group_name, "${var.cluster_owner}-${random_string.random_string.result}-rg")
}

locals {
  resource_group = {
    name     = var.create_resource_group ? azurerm_resource_group.main[0].name : var.resource_group_name
    location = var.location
  }
  owner_and_random_string = "${var.cluster_owner}-${random_string.random_string.result}"
}

resource "azurerm_virtual_network" "vnet" {
  address_space       = ["10.52.0.0/16"]
  location            = local.resource_group.location
  name                = "${local.owner_and_random_string}-vn"
  resource_group_name = local.resource_group.name
}

resource "azurerm_subnet" "subnet" {
  address_prefixes                          = ["10.52.0.0/24"]
  name                                      = "${local.owner_and_random_string}-sn"
  resource_group_name                       = local.resource_group.name
  virtual_network_name                      = azurerm_virtual_network.vnet.name
  private_endpoint_network_policies_enabled = true
}

resource "azurerm_user_assigned_identity" "user_identity" {
  location            = local.resource_group.location
  name                = "${local.owner_and_random_string}-identity"
  resource_group_name = local.resource_group.name
}

# # Just for demo purpose, not necessary to named cluster.
# resource "azurerm_log_analytics_workspace" "main" {
#   location            = local.resource_group.location
#   name                = "prefix-workspace"
#   resource_group_name = local.resource_group.name
#   retention_in_days   = 30
#   sku                 = "PerGB2018"
# }

module "aks" {
  source                            = "Azure/aks/azurerm"
  version                           = "6.6.0"
  cluster_name                      = "${local.owner_and_random_string}-test-cluster"
  prefix                            = var.cluster_owner
  resource_group_name               = local.resource_group.name
  admin_username                    = null
  azure_policy_enabled              = true
  agents_size                       = var.machine_type
  agents_count                      = var.node_count
  location                          = var.location
  agents_availability_zones         = var.zones
  identity_ids                      = [azurerm_user_assigned_identity.user_identity.id]
  identity_type                     = "UserAssigned"
  private_cluster_enabled           = false
  net_profile_pod_cidr              = "10.1.0.0/16"
  rbac_aad_managed                  = true
  role_based_access_control_enabled = true
  # disk_encryption_set_id    = azurerm_disk_encryption_set.des.id
  # cluster_log_analytics_workspace_name = "test-cluster"
  log_analytics_workspace_enabled = false
  # log_analytics_workspace = {
  #   id   = azurerm_log_analytics_workspace.main.id
  #   name = azurerm_log_analytics_workspace.main.name
  # }
  # maintenance_window = {
  #   allowed = [
  #     {
  #       day   = "Sunday",
  #       hours = [22, 23]
  #     },
  #   ]
  #   not_allowed = []
  # }
}
