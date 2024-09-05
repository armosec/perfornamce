locals {
  random       = random_string.suffix.result
  owner        = var.owner
  vpc_name     = "vpc-test-${local.owner}-${local.random}"
  cluster_name = "${local.owner}-test-${local.random}"
}