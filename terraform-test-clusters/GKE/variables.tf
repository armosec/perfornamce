variable "project_id" {
  description = "The project ID to host the cluster in"
  default     = "armo-test-clusters"
}

variable "cluster_name_suffix" {
  description = "A suffix to append to the default cluster name"
  default     = ""
}

variable "region" {
  description = "The region to host the cluster in"
}

variable "network" {
  description = "The VPC network to host the cluster in"
}

variable "subnetwork" {
  description = "The subnetwork to host the cluster in"
}

variable "ip_range_pods" {
  description = "The secondary ip range to use for pods"
}

variable "ip_range_services" {
  description = "The secondary ip range to use for services"
}

# variable "compute_engine_service_account" {
#   description = "Service account to associate to the nodes in the cluster"
# }

variable "skip_provisioners" {
  type        = bool
  description = "Flag to skip local-exec provisioners"
  default     = false
}

variable "enable_binary_authorization" {
  description = "Enable BinAuthZ Admission controller"
  default     = false
}

variable "kubernetes_version" {
  description = "Kubernetes version"
}

variable "cluster_type" {
  description = "Cluster type"
}

variable "node_count" {
  type        = number
  description = "Desired size of worker nodes per AZ"
  default     = 1
}