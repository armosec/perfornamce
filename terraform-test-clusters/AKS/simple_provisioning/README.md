# ARMO Terraform test cluster - AKS - Simple Provisioning


The AKS Terraform project will create for you a regional AKS cluster in the "North Europe" reagion under the "Azure subscription B - AKS" subscription. the cluster will be created with your name + random string as a suffix to prevent conflicts between other clusters/resources.

### Prerequisites:

To use Terraform project, you need:

1. [azure-cli](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=apt) installed in your machine then you need to login to your Azure account. you can [login](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli) to your account by running the following command: 
<code>az login</code>
2. [Terraform](https://developer.hashicorp.com/terraform/downloads) installed in your machine.
3. Permmision to use the dedicated subscription_id for test clusters in Azure


### How to use

1. Clone this GitHub repo to your machine:
    ```sh
    git clone git@github.com:armosec/terraform-test-clusters.git
    ```

2. Enter into the AKS Simple Provisioning folder
    ```sh
    cd terraform-test-clusters/AKS/simple_provisioning
    ```

3. Change in the ```terraform.tfvars``` file your name under the “cluster_owner” value.

4. Run ```terraform init``` to initialize the project and download the dependencies.

5. Run ```terraform plan``` to see what terraform will be going to create/change/replace/destroy.

6. To apply the changes, run ```terraform apply``` and type “yes”. **you must keep your terminal on when you are running this operation, otherwise, it’s will be canceled.**

7. When Terraform finished creating all the resources, run the following commands:
    * To set the Subscription ID as default:
        ```sh
        az account set --subscription $(terraform output -raw subscription_id)
        ```
    * To connect to your new AKS cluster: 
        ```sh
        az aks get-credentials --resource-group $(terraform output -raw resource_group_name) --name $(terraform output -raw kubernetes_cluster_name)
        ```

8. When you finished with your tests, run ```terraform destroy``` and type “yes”. **you must keep your terminal on when you are running this operation, otherwise, it’s will be canceled.**


### Scaling the node pools:

* To scale down the node pools to 0 worker nodes run the following command:
    ```sh
    az vmss scale --resource-group $(terraform output -raw mc_rg) --name $(az vmss list --resource-group $(terraform output -raw mc_rg) |jq -r '.[].name') --new-capacity 0
    ```
* To scale up the node pools again (default: 3 worker nodes) just run again: 
    ```terraform apply```


### Important
When you run ```terraform apply```, terraform will create a tf.state file. This file is important for you, it’s synced with the state of the resources that you just created in the cloud. DO NOT remove it before you run ```terraform destroy```, otherwise, you need to manually delete all the resources that you created via the AWS console.
