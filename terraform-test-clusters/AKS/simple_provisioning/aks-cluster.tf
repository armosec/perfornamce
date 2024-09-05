resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

locals {
  random       = random_string.suffix.result
  owner        = var.cluster_owner
  cluster_name = "${local.owner}-${local.random}"
}

resource "azurerm_resource_group" "rg" {
  name     = "${local.cluster_name}-rg"
  location = var.region

  tags = {
    environment = "test-rg"
    owner       = "${local.owner}"
    suffix      = "${local.random}"
  }
}

resource "azurerm_kubernetes_cluster" "aks" {
  name                = "${local.cluster_name}-aks"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  # kubernetes_version                = var.kubernetes_version ## enable it to specify the AKS Kubernetes version
  dns_prefix                        = "${local.cluster_name}-k8s"
  role_based_access_control_enabled = true

  default_node_pool {
    name                = "default"
    node_count          = var.node_count
    enable_auto_scaling = false
    min_count           = null
    max_count           = null
    vm_size             = var.machine_type
    os_disk_size_gb     = 30
    zones               = var.zones
  }

  identity {
    type = "SystemAssigned"
  }

  tags = {
    environment = "test-cluster"
    owner       = "${local.owner}"
    suffix      = "${local.random}"
  }
}

#### Spot node pool (optional):
# resource "azurerm_kubernetes_cluster_node_pool" "spot_node_pool" {
#   name                  = "internal"
#   kubernetes_cluster_id = azurerm_kubernetes_cluster.aks.id
#   vm_size               = var.spot_machine_type
#   node_count            = var.spot_node_count
#   priority              = "Spot"
#   eviction_policy       = "Delete"
#   spot_max_price        = var.spot_max_price
#   tags = {
#     environment = "test-cluster"
#     owner       = "${local.owner}"
#     suffix      = "${local.random}"
#   }
# }

### Service principal (Optional)
# service_principal {
#   client_id     = var.appId
#   client_secret = var.password
# }


data "azurerm_client_config" "current" {
}

# get MC Resource Group
data "azurerm_resource_group" "aks_mc_rg" {
  depends_on = [azurerm_kubernetes_cluster.aks]
  name       = azurerm_kubernetes_cluster.aks.node_resource_group
}