variable "create_resource_group" {
  type     = bool
  default  = true
  nullable = false
}

variable "key_vault_firewall_bypass_ip_cidr" {
  type    = string
  default = null
}

variable "location" {
  default = "eastus"
}

variable "managed_identity_principal_id" {
  type    = string
  default = null
}

variable "resource_group_name" {
  type    = string
  default = null
}

variable "cluster_owner" {
  type = string
}

variable "node_count" {
  description = "Worker node number"
}

variable "machine_type" {
  description = "Machine type for AKS worker nodes"
}

variable "zones" {
  description = "The availiabilty zones"
}

variable "subscription_id" {
  description = "Azure Subscription ID"
}