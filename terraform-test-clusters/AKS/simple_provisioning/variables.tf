# variable "appId" {
#   description = "Azure Kubernetes Service Cluster service principal"
# }

# variable "password" {
#   description = "Azure Kubernetes Service Cluster password"
# }

variable "cluster_owner" {
  description = "Azure Kubernetes Service Owner"
}

variable "subscription_id" {
  description = "Azure Subscription ID"
}

variable "region" {
  description = "Resource group and AKS cluster region"
}

variable "node_count" {
  description = "Worker node number"
}

variable "machine_type" {
  description = "Machine type for the default AKS worker nodes"
}

variable "spot_node_count" {
  description = "Spot node pool - worker node number"
}

variable "spot_machine_type" {
  description = "Machine type for the spot node pool"
}

variable "spot_max_price" {
  description = "Maximum price for spot machine"
}

variable "zones" {
  description = "The availiabilty zones"
}

## enable it to specify the AKS Kubernetes version

# variable "kubernetes_version" {
#   description = "AKS Kubernetes version"
# }
