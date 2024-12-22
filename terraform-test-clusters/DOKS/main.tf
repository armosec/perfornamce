# General Purpose Droplets
# s-2vcpu-2gb: 2 vCPUs, 2 GB RAM
# s-4vcpu-8gb: 4 vCPUs, 8 GB RAM
# s-8vcpu-16gb: 8 vCPUs, 16 GB RAM
# s-16vcpu-32gb: 16 vCPUs, 32 GB RAM

variable "node_size" {
  description = "Size of the nodes"
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "node_count" {
  description = "Number of nodes in the default node pool"
  type        = number
  default     = 2
}

variable "min_nodes" {
  description = "Minimum number of nodes for auto-scaling"
  type        = number
  default     = 2
}

variable "max_nodes" {
  description = "Maximum number of nodes for auto-scaling"
  type        = number
  default     = 2
}

module "vpc" {
  source = "git::ssh://git@github.com/armosec/armo-terraform-modules//do-modules/vpc?ref=main"
  vpc_name   = "performance"
  region     = "fra1"
  cidr_block = "10.222.0.0/16"
}

module "k8s-cluster" {
  source = "git::ssh://git@github.com/armosec/armo-terraform-modules//do-modules/doks?ref=main"
  cluster_name = "performance"
  region       = "fra1"
  vpc_uuid     = module.vpc.vpc_id
  k8s_version  = "1.31"

  # Default node pool
  node_pool_name = "default"
  node_size      = var.node_size
  node_count     = var.node_count
  auto_scale     = false
  min_nodes      = var.min_nodes
  max_nodes      = var.max_nodes
  default_node_pool_labels = {
    "arc-node-group" = "default"
  }
}

module "gh-runners" {
  source = "git::ssh://git@github.com/armosec/armo-terraform-modules//do-modules/gh-runners?ref=main"
  cluster_host           = module.k8s-cluster.cluster_host
  cluster_token          = module.k8s-cluster.cluster_token
  cluster_ca_certificate = module.k8s-cluster.cluster_ca_certificate
}
