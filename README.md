# EKS Cluster Automation and Microservices Deployment

This Python script automates the creation of an AWS EKS cluster using Terraform, deploys microservices across multiple namespaces, installs Prometheus, Kubescape, and Pyroscope, and allows for cluster destruction once testing is complete. It also checks for any pods in `CrashLoopBackOff` state and handles parallel application of services.

## Features

- Create an EKS cluster using Terraform with `m5.xlarge` EC2 instances.
- Scale the number of nodes in the cluster dynamically.
- Create twice as many namespaces as the number of nodes in the cluster.
- Deploy microservices across multiple namespaces in parallel.
- Install Prometheus stack for monitoring.
- Install Pyroscope for profiling.
- Optionally skip the cluster creation and only connect to an existing cluster.
- Apply Kubescape security scanning and runtime threat detection.
- Destroy the cluster and associated infrastructure.
- Monitor and validate pod stability by detecting `CrashLoopBackOff` pods.

## Prerequisites

Before running the script, ensure the following tools are installed:

- [AWS CLI](https://aws.amazon.com/cli/) (for connecting to EKS)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) (for managing Kubernetes clusters)
- [Python 3.x](https://www.python.org/downloads/) (for running the script)
- [Terraform](https://www.terraform.io/) (for infrastructure provisioning)
- [Helm](https://helm.sh/) (for deploying Kubernetes applications)

## Installation

 **Clone the repository**:

```bash
git clone https://github.com/armosec/performance.git
cd performance
```

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `-nodes` | int | 3 | Specifies the number of nodes for the EKS cluster. The script adds one extra node. |
| `-kdr` | flag | False | Enable Kubescape runtime detection capabilities. |
| `-destroy` | flag | False | Destroys the Terraform-managed infrastructure, including the EKS cluster. |
| `-skip-cluster` | flag | False | Skips the cluster creation and only connects to an existing EKS cluster. |
| `-account` | string | Required | The account ID for deploying Kubescape. |
| `-accessKey` | string | Required | The access key for deploying Kubescape. |
| `-version` | string | Latest | Specify the Helm chart version for Kubescape. |
| `-storage-version` | string | Latest | Specify the storage image version. |
| `-node-agent-version` | string | Latest | Specify the node agent image version. |
| `-private-node-agent` | string | Latest | Specify the private node agent version. |
| `-helm-git-branch` | string | N/A | Git branch or repository URL for custom Helm chart deployment. |

## Usage

### 1. Create an EKS cluster with a specific number of nodes

```bash
python performance.py -nodes 10
```

### 2. Create an EKS cluster with a specific number of nodes and enable KDR

```bash
python performance.py -nodes 10 -kdr
```

### 3. Skip Cluster Creation and Connect to an Existing Cluster

```bash
python performance.py -skip-cluster
```

### 4. Create cluster and apply Kubescape with account ID and Access Key

```bash
python performance.py -nodes 10 -account <your-account-id> -accessKey <your-access-key>
```

### 5. Apply a specific version of Kubescape

```bash
python performance.py -nodes 10 -account <your-account-id> -accessKey <your-access-key> -version <version>
```

### 6. Destroy the cluster

```bash
python performance.py -destroy
```

> **Note:** When running `terraform destroy`, keep your terminal open, or the operation will be canceled.

## Additional Features


### Exposing Grafana and Retrieving the Admin Secret
After deploying the Prometheus stack with Grafana, you can expose Grafana and retrieve the admin password using the following steps:

1. **Expose Grafana using port-forwarding:**

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

This forwards port `3000` on your local machine to port `80` of the Grafana service. Access Grafana by visiting `http://localhost:3000` in your browser.

2. **Retrieve the Grafana admin password:**

```bash
kubectl get secret -n monitoring kube-prometheus-stack-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
```

This will output the Grafana admin password, which you can use to log in.