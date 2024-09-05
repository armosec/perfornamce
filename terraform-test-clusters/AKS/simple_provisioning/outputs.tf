output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

output "kubernetes_cluster_name" {
  value = azurerm_kubernetes_cluster.aks.name
}

output "subscription_id" {
  description = "Run the following command to set the subscription ID"
  value       = var.subscription_id
}

output "set_subscription_id" {
  description = "Run the following command to set the subscription ID"
  value       = "az account set --subscription $(terraform output -raw subscription_id)"
}

output "connect_to_cluster" {
  description = "Run the following command to connect to the cluster"
  value       = "az aks get-credentials --resource-group $(terraform output -raw resource_group_name) --name $(terraform output -raw kubernetes_cluster_name)"
}

output "mc_rg" {
  # description = "Run the following command to connect to the cluster"
  value = data.azurerm_resource_group.aks_mc_rg.name
}

# output "host" {
#   value = azurerm_kubernetes_cluster.default.kube_config.0.host
# }

# output "client_key" {
#   value = azurerm_kubernetes_cluster.default.kube_config.0.client_key
# }

# output "client_certificate" {
#   value = azurerm_kubernetes_cluster.default.kube_config.0.client_certificate
# }

# output "kube_config" {
#   value = azurerm_kubernetes_cluster.default.kube_config_raw
# }

# output "cluster_username" {
#   value = azurerm_kubernetes_cluster.default.kube_config.0.username
# }

# output "cluster_password" {
#   value = azurerm_kubernetes_cluster.default.kube_config.0.password
# }
