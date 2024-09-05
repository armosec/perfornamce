output "kubernetes_endpoint" {
  sensitive = true
  value     = module.gke.endpoint
}

output "client_token" {
  sensitive = true
  value     = base64encode(data.google_client_config.default.access_token)
}

output "ca_certificate" {
  sensitive = true
  value = module.gke.ca_certificate
}

output "service_account" {
  description = "The default service account used for running nodes."
  value       = module.gke.service_account
}

output "project_id" {
  description = "Project ID"
  value       = var.project_id
}

output "name" {
  description = "Cluster name"
  value       = module.gke.name
}

output "region" {
  description = "Cluster region"
  value       = module.gke.region
}

output "connect_to_cluster" {
  description = "Run the following command to connect to the cluster"
  value       = "gcloud container clusters get-credentials $(terraform output -raw name) --region $(terraform output -raw region) --project $(terraform output -raw project_id)"
}

