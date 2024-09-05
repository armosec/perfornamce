# ARMO Terraform test cluster - GKE


The GKE Terraform project will create for you a regional GKE cluster in the ״me-west1״ region (Tel-Aviv) under the project ID: “armo-test-clusters”. the cluster will be created with your name as a suffix to prevent conflicts between other clusters/resources.

### Prerequisites:

To use Terraform project, you need:

1. [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed in your machine then you need to login to your GCP account. you can [login](https://cloud.google.com/sdk/gcloud/reference/auth/login) to your account by running the following command: 
<code>gcloud auth login</code>
2. [Terraform](https://developer.hashicorp.com/terraform/downloads) installed in your machine.


### How to use

1. clone this GitHub repo to your machine:
    <code>git clone git@github.com:armosec/terraform-test-clusters.git</code>

2. cd into the GKE folder
<code>cd terraform-test-clusters/GKE/</code>

3. Change in the ```terraform.tfvars``` file your name under the “cluster_name_suffix” value.

4. Run ```terraform init``` to initialize the project and download the dependencies.

5. Run ```terraform plan``` to see what terraform will be going to create/change/replace/destroy.

6. To apply the changes, run ```terraform apply``` and type “yes”. **you must keep your terminal on when you are running this operation, otherwise, it’s will be canceled.**

7. When Terraform finished creating all the resources, run the following command to connect to your new GKE cluster: 
    ```gcloud container clusters get-credentials $(terraform output -raw name) --region $(terraform output -raw region) --project $(terraform output -raw project_id)```

8. When you finished with your tests, run ```terraform destroy``` and type “yes”. **you must keep your terminal on when you are running this operation, otherwise, it’s will be canceled.**


### Scaling the node pools:

* To scale down the node pools to 0 worker nodes run the following command and type "yes": 
    <code>terraform apply -var=node_count=0</code>
* To scale up the node pools again (default: 1 worker node per AZ = 3 worker nodes) run: 
    <code>terraform apply</code>


### Important
When you run ```terraform apply```, terraform will create a tf.state file. This file is important for you, it’s synced with the state of the resources that you just created in the cloud. DO NOT remove it before you run ```terraform destroy```, otherwise, you need to manually delete all the resources that you created via the AWS console.


**This GKE Terraform project has been created using the official GKE Terraform module.**