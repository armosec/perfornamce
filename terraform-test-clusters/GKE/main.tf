locals {
  cluster_name          = "${var.cluster_type}-cluster-${var.cluster_name_suffix}"
}

data "google_client_config" "default" {}

module "gke" {
  source                      = "terraform-google-modules/kubernetes-engine/google"
  version                     = "24.1.0"
  kubernetes_version          = var.kubernetes_version
  project_id                  = var.project_id
  name                        = local.cluster_name
  regional                    = true
  region                      = var.region
  network                     = var.network
  subnetwork                  = var.subnetwork
  ip_range_pods               = var.ip_range_pods
  ip_range_services           = var.ip_range_services
  create_service_account      = true
  # service_account             = var.compute_engine_service_account
  enable_cost_allocation      = true
  enable_binary_authorization = var.enable_binary_authorization
  skip_provisioners           = var.skip_provisioners

  node_pools = [
    {
      name                      = "default-node-pool"
      machine_type              = "e2-standard-2"
      node_count                = var.node_count # number of worker node per AZ
      disk_size_gb              = 50
      disk_type                 = "pd-standard"
      image_type                = "COS_CONTAINERD"
      enable_gcfs               = false
      enable_gvnic              = false
      auto_repair               = false
      autoscaling               = false
      spot                      = false
      # initial_node_count        = 1 # availble only when autoscaling is true 
      # min_count                 = 0
      # max_count                 = 2
      # node_locations            = "us-central1-b,us-central1-c"
      # local_ssd_count           = 0
      # auto_upgrade              = true
      # service_account           = "project-service-account@<PROJECT ID>.iam.gserviceaccount.com"
      # preemptible               = false
    },
    # {
    #   name                      = "node-pool-2"
    #   machine_type              = "e2-standard-2"
    #   # node_locations            = "us-central1-b,us-central1-c"
    #   min_count                 = 1
    #   max_count                 = 3
    #   # local_ssd_count           = 0
    #   spot                      = false
    #   disk_size_gb              = 50
    #   disk_type                 = "pd-standard"
    #   image_type                = "COS_CONTAINERD"
    #   enable_gcfs               = false
    #   enable_gvnic              = false
    #   # auto_repair               = true
    #   # auto_upgrade              = true
    #   # service_account           = "project-service-account@<PROJECT ID>.iam.gserviceaccount.com"
    #   # preemptible               = false
    #   initial_node_count        = 1
    # },
  ]

  node_pools_oauth_scopes = {
    all = [
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
    ]
  }

  node_pools_labels = {
    all = {
      name = local.cluster_name
      owner = var.cluster_name_suffix
    }

    default-node-pool = {
      default-node-pool = true
    }
  }

  node_pools_metadata = {
    all = {}

    default-node-pool = {
      node-pool-metadata-custom-value = "my-node-pool"
    }
  }

  node_pools_taints = {
    all = []

    default-node-pool = [
      {
        key    = "default-node-pool"
        value  = true
        effect = "PREFER_NO_SCHEDULE"
      },
    ]
  }

  node_pools_tags = {
    all = []

    default-node-pool = [
      "default-node-pool",
    ]
  }
}
