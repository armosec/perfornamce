output "cluster_name" {
  description = "Kubernetes Cluster Name"
  value       = local.cluster_name
}

output "region" {
  description = "AWS region"
  value       = var.region
}

output "connect_to_cluster" {
  description = "Run the following command to connect to the cluster"
  value       = "aws eks --region $(terraform output -raw region) update-kubeconfig --name $(terraform output -raw cluster_name)"
}

# output "az" {
#   description = "Run the following command to connect to the cluster"
#   value       = data.aws_availability_zones.available.names
# }


output "cluster_info" {
  description = "Run the following command to connect to the cluster"
  value       = aws_eks_cluster.eks_cluster.identity[0].oidc[0].issuer
}

