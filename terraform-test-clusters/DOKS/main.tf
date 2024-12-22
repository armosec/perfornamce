# General Purpose Droplets
# s-2vcpu-2gb: 2 vCPUs, 2 GB RAM
# s-4vcpu-8gb: 4 vCPUs, 8 GB RAM
# s-8vcpu-16gb: 8 vCPUs, 16 GB RAM
# s-16vcpu-32gb: 16 vCPUs, 32 GB RAM

# terraform apply -var="k8s_version=${{ github.event.inputs.K8s-ver }}" " 

module "vpc" {
  source = "git::ssh://git@github.com/armosec/armo-terraform-modules//do-modules/vpc?ref=main"
  vpc_name   = "performance"
  region     = "fra1"
  cidr_block = "10.111.0.0/16"
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
  min_nodes      = var.node_count
  max_nodes      = var.node_count
#  default_node_pool_labels = {
#    "arc-node-group" = "default"
#  }
}

module "gh-runners" {
  source = "git::ssh://git@github.com/armosec/armo-terraform-modules//do-modules/gh-runners?ref=main"
  cluster_host           = module.k8s-cluster.cluster_host
  cluster_token          = module.k8s-cluster.cluster_token
  cluster_ca_certificate = module.k8s-cluster.cluster_ca_certificate
}
