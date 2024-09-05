output "test_aks_named_id" {
  value = module.aks.aks_id
}

output "test_aks_named_identity" {
  sensitive = true
  value     = try(module.aks.cluster_identity, "")
}

output "resource_group_name" {
  value = azurerm_resource_group.main[0].name
}

output "kubernetes_cluster_name" {
  value = module.aks.aks_name
}

output "mc_resource_group_name" {
  value = module.aks.node_resource_group
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
  value       = "az aks get-credentials --resource-group $(terraform output -raw resource_group_name) --name $(terraform output -raw kubernetes_cluster_name) --admin"
}