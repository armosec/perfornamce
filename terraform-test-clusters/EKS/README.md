# ARMO Terraform test cluster - EKS

The EKS Terraform project will create for you a full EKS cluster in the ״eu-west-2״ region (London) with your name and random suffix to prevent conflicts between resources

### Prerequisites:

To use Terraform project, you need:

1. [AWS cli](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured with a set of credentials of our AWS-dev account (such as cadeveloper). you can configure it by running the following command: 
<code>aws configure</code>
2. [Terraform](https://developer.hashicorp.com/terraform/downloads) installed in your machine.


### How to use

1. clone this GitHub repo to your machine:
    <code>git clone git@github.com:armosec/terraform-test-clusters.git</code>

2. cd into the EKS folder
<code>cd terraform-test-clusters/EKS/</code>

3. Change in the ```variables.tf``` file your name in the “owner” variable.

4. Run ```terraform init``` to initialize the project and download the dependencies.

5. Run ```terraform plan``` to see what terraform will be going to create/change/replace/destroy.

6. To apply the changes, run ```terraform apply``` and type “yes”. **you must keep your terminal on when you are running this operation, otherwise, it’s will be canceled.**

7. When Terraform finished to create all the resources, run the following command to connect to your new EKS cluster: 
    ```aws eks --region $(terraform output -raw region) update-kubeconfig --name $(terraform output -raw cluster_name)```

8. When you finished with your tests, run ```terraform destroy``` and type “yes”. **you must keep your terminal on when you are running this operation, otherwise, it’s will be canceled.**


### Scaling the node group:

* To scale down the node group to 0 worker nodes run the following command and type "yes": 
    <code>terraform apply -var=desired_size=0</code>
* To scale up the node group again (default: 2 worker nodes) run: 
    <code>terraform apply</code>



### Important
When you run ```terraform apply```, terraform will create a tf.state file. This file is important for you, it’s synced with the state of the resources that you just created in the cloud. DO NOT remove it before you run ```terraform destroy```, otherwise, you need to manually delete all the resources that you created via the AWS console.