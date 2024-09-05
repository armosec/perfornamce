# EKS Cluster Automation and Microservices Deployment

This Python script automates the creation of an AWS EKS cluster using Terraform, deploys microservices across multiple namespaces, installs Prometheus and Kubescape, and allows for cluster destruction once testing is complete. It also checks for any pods in `CrashLoopBackOff` state and handles parallel application of services.


## Features

- Create an EKS cluster using Terraform with `m5.xlarge` EC2 instances.
- Scale the number of nodes in the cluster dynamically.
- Create twice as many namespaces as the number of nodes in the cluster
- Deploy microservices across multiple namespaces in parallel.
- Install Prometheus stack for monitoring.
- Optionally skip the cluster creation and only connect to an existing cluster.
- Apply  Kubescape.
- Destroy the cluster and associated infrastructure.

## Prerequisites

Before running the script, ensure the following tools are installed:

- [AWS CLI](https://aws.amazon.com/cli/) (for connecting to EKS)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) (for managing Kubernetes clusters)
- [Python 3.x](https://www.python.org/downloads/) (for running the script)

## Installation

 **Clone the repository**:


    git clone https://github.com/your-username/P.git
    cd project-name


## Arguments


Argument	Type	Default	Description	Example

`-nodes` : Specifies the number of nodes for the EKS cluster. The script will add 1 more node to this number (The deaful is 2)

`-kdr`	:Enable Kubescape runtime detection capabilities during the installation of "kubescpe".	

`-destroy`	:Destroys the Terraform-managed infrastructure, including the EKS cluster.

`-skip-cluster`	:Skips the cluster creation and only connects to an existing EKS cluster.

`-account`: The account ID for deploying Kubescape. Required when deploying Kubescape.

`-accessKey`:	The access key for deploying Kubescape. Required when deploying Kubescape.

`-version`	: Specify the version of Kubescape to be deployed. If not provided, the latest version is used.

## Usage


1. To create an EKS cluster with a specific number of nodes, use the following command:

    ```bash
    python performance.py -nodes 10 
    
2. To create an EKS cluster with a specific number of nodes and enable KDR

    ```bash
    python performance.py - nodes 10 -kdr

3. Skip Cluster Creation and Connect to an Existing Cluster:
    ```bash
    python performance.py -skip-cluster

4. Create cluster and apply "Kubescape", you need account ID and Access key

    ```bash
    python performance.py -nodes 10 -account <your-account-id> -accessKey <your-access-key>

5. Apply spesific version of "Kubescape"

    ```bash
    python performance.py -nodes 10 -account <your-account-id> -accessKey <your-access-key> -version <version>


6. To destroy the cluater 

    ```bash
    python performance.py -destroy

** when you run ``terraform destroy``,  you must keep your terminal on when you are running this operation, otherwise, it’s will be canceled.

**note**:

*  **Provisioning an additional node for Prometheus and Kubescape:**
    The script will provision one extra node beyond the specified number of nodes in the cluster. This additional node is reserved for deploying Prometheus and Kubescape and is not used in the namespace calculation. The namespaces are created based on twice the number of originally specified nodes, without including the extra node for Prometheus and Kubescape.

    For example, if you specify 5 nodes, the script will provision 6 nodes but calculate namespaces as 2 * 5, resulting in 10 namespaces.


### Exposing Grafana and Retrieving the Admin Secret
After deploying the Prometheus stack with Grafana, you can expose Grafana and retrieve the admin password using the following steps:

1. Expose Grafana using port-forwarding:
To make Grafana accessible from your local machine, use the following kubectl port-forward command:

    ```bash

    kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80

This will forward port 3000 on your local machine to port 80 of the Grafana service. You can now access Grafana by visiting http://localhost:3000 in your browser.

2. Retrieve the Grafana admin password:
To get the Grafana admin password, run the following command:

    ```bash
    kubectl get secret -n monitoring kube-prometheus-stack-grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo
    
This will output the Grafana admin password, which you can use to log in.