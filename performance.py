import os
import time
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

        
def run_command(command, cwd=None):
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, shell=True, cwd=cwd)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        exit(1)
        
# Step 1: set up the EKS cluster with Terraform and AWS CLI commands
def setup_cluster(node_count):
    terraform_dir = os.path.join("terraform-test-clusters", "EKS")
    try:
        print("Initializing Terraform...")
        run_command('terraform init', terraform_dir)
        print("Planning Terraform configuration...")
        run_command('terraform plan', terraform_dir)
        node_count = node_count +1
        print(f"Applying Terraform configuration with {node_count} nodes...")
        run_command(f'terraform apply -auto-approve -var=desired_size={node_count}', terraform_dir)
        return node_count
    
    except subprocess.CalledProcessError as e:
        print(f"Failed to set up EKS cluster with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        exit(1)
        
def connect_to_eks_cluster(region, cluster_name, terraform_dir):
    try:
        # Print the command that will be executed
        command = f"aws eks --region {region} update-kubeconfig --name {cluster_name}"
        print(f"Executing: {command}")
        
        # Execute the command
        subprocess.run(command, check=True, shell=True)
        print("Successfully connected to the EKS cluster.")
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to connect to EKS cluster with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        exit(1)
        
def deploy_kube_prometheus_stack():
    try:
        # Define paths relative to the script's directory
        values_file = "./Monitoring/values/kube-prometheus-stack.yaml"
        chart_path = "./Monitoring/kube-prometheus-stack"
        
        # Construct the Helm command
        helm_command = (
            f"helm upgrade --install kube-prometheus-stack "
            f"-f {values_file} "
            f"{chart_path} "
            f"-n monitoring --create-namespace"
        )
        
        # Run the command
        print("Deploying kube-prometheus-stack using Helm...")
        run_command(helm_command)
        print("kube-prometheus-stack deployed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to deploy kube-prometheus-stack with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        exit(1)

        
def create_namespace(namespace_name):
    try:
        subprocess.run(['kubectl', 'create', 'namespace', namespace_name], check=True)
        print(f"Created namespace: {namespace_name}")
        return namespace_name
    except subprocess.CalledProcessError as e:
        print(f"Failed to create namespace {namespace_name} with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        return None

def create_parallel_namespaces(node_count, skip_cluster=False):
    try:
        if skip_cluster:
            # Get the number of nodes in the cluster
            result = subprocess.run(
                ['kubectl', 'get', 'nodes', '--no-headers'],
                check=True, capture_output=True, text=True
            )
            total_nodes = len(result.stdout.splitlines())
            num_namespaces = (total_nodes - 1) * 2
        else:
            # Calculate the number of namespaces to create 
            num_namespaces = (node_count - 1) * 2

        print(f"Creating {num_namespaces} namespaces")

        # Create namespace names list
        namespace_list = [f"namespace-{i+1}" for i in range(num_namespaces)]

        # Use ThreadPoolExecutor to create namespaces in parallel
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_namespace = {executor.submit(create_namespace, ns): ns for ns in namespace_list}
            created_namespaces = []

            for future in as_completed(future_to_namespace):
                namespace = future_to_namespace[future]
                result = future.result()
                if result:
                    created_namespaces.append(result)

        print("All namespaces created successfully.")
        return created_namespaces

    except subprocess.CalledProcessError as e:
        print(f"Failed to create namespaces with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        exit(1)

# def apply_microservices_demo(namespaces):
#     microservices_demo_path = os.path.join("microservices-demo", "release", "kubernetes-manifests.yaml")
#     for namespace in namespaces:
#         print(f"Applying microservices-demo to namespace {namespace}...")
#         try:
#             run_command(f'kubectl apply -f {microservices_demo_path} -n {namespace}')
#             print(f"Successfully applied microservices-demo to namespace {namespace}.")
#         except subprocess.CalledProcessError as e:
#             print(f"Failed to apply microservices-demo to namespace {namespace}: {e}")
#             exit(1)

# Function to run kubectl apply for a single namespace
def apply_microservices_demo_to_namespace(namespace, microservices_demo_path):
    print(f"Applying microservices-demo to namespace {namespace}...")
    try:
        result = subprocess.run(f'kubectl apply -f {microservices_demo_path} -n {namespace}', 
                                check=True, capture_output=True, text=True, shell=True)
        print(f"Successfully applied microservices-demo to namespace {namespace}.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply microservices-demo to namespace {namespace}: {e.stderr}")
        return False

# Function to apply the microservices demo to all namespaces in parallel
def apply_microservices_demo(namespaces):
    microservices_demo_path = os.path.join("microservices-demo", "release", "kubernetes-manifests.yaml")

    # Use ThreadPoolExecutor for parallel execution
    with ThreadPoolExecutor(max_workers=min(20, len(namespaces))) as executor: # Limit to 20 workers
        futures = {executor.submit(apply_microservices_demo_to_namespace, ns, microservices_demo_path): ns for ns in namespaces}

        for future in as_completed(futures):
            namespace = futures[future]
            try:
                result = future.result()  # Will raise exception if apply failed
                if result:
                    print(f"Namespace {namespace}: Applied successfully.")
                else:
                    print(f"Namespace {namespace}: Failed to apply.")
            except Exception as e:
                print(f"Namespace {namespace}: Exception occurred: {e}")


# Step 2: Deploy Kubescape using Helm
def deploy_kubescape(account, accessKey, version=None, enable_kdr=False):
    try:
        print("Adding Kubescape Helm repository...")
        run_command('helm repo add kubescape https://kubescape.github.io/helm-charts/')
        run_command('helm repo update')
        
        print("Deploying Kubescape Operator...")
        cluster_context = subprocess.run(['kubectl', 'config', 'current-context'], check=True, capture_output=True, text=True).stdout.strip()
        
        helm_command = (
            f'helm upgrade --install kubescape kubescape/kubescape-operator '
            f'-n kubescape --create-namespace '
            f'--set clusterName={cluster_context} '
            f'--set account={account} '
            f'--set accessKey={accessKey} '
            f'--set server=api.armosec.io'
        )
        
        if version:
            helm_command += f' --version {version}'
            
        # Add the additional Helm parameters if -kdr is enabled
        if enable_kdr:
            additional_params = (
                '--set capabilities.runtimeDetection=enable '
                '--set capabilities.malwareDetection=enable '
                '--set capabilities.nodeProfileService=enable '
                '--set alertCRD.scopeClustered=true '
                '--set alertCRD.installDefault=true'
            )
            helm_command += ' ' + additional_params
        
        run_command(helm_command)
        time.sleep(30)  # Wait for the operator to deploy
        print("waiting for operator to deploy - 30 sec")
        print("Kubescape Operator deployed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to deploy Kubescape with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        exit(1)        

# Step 3: Wait for the cluster to be ready
def check_cluster_ready(timeout=300):  # Timeout 5 min
    start_time = time.time()  

    while True:
        elapsed_time = time.time() - start_time  

        if elapsed_time > timeout:
            print(f"Timeout exceeded! Waited for {timeout / 60} minutes.")
            break

        try:
            result = subprocess.run(
                ['kubectl', 'get', 'pods', '-A'],
                check=True, capture_output=True, text=True
            )

            # Process each line of the output
            all_pods_ready = True
            total_pods = 0
            pods_ready = 0

            for line in result.stdout.splitlines()[1:]:  # Skip the header line
                total_pods += 1
                columns = line.split()

                ready_ratio = columns[2]
                ready, total = map(int, ready_ratio.split('/'))

                # Check if the pod is in the "Running" state and all containers are ready
                if columns[3] == "Running" and ready == total:
                    pods_ready += 1
                else:
                    all_pods_ready = False

            if all_pods_ready and total_pods == pods_ready:
                print(f"All {total_pods} pods are running and ready.")
                break
            else:
                print(f"Waiting for all pods to be ready... ({pods_ready}/{total_pods})")
        
        except subprocess.CalledProcessError as e:
            print("Cluster not ready yet, retrying...")

        # Sleep for 10 seconds before checking again
        time.sleep(10)

        
# Step 4: Check for pods in CrashLoopBackOff state using kubectl
def check_crashloop_pods(namespace='default'):
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'pods', '-n', namespace], 
            check=True, capture_output=True, text=True
        )

        all_pods_stable = True
        total_pods = 0
        stable_pods = 0

        for line in result.stdout.splitlines()[1:]: 
            total_pods += 1
            columns = line.split()

            pod_name = columns[0]
            pod_status = columns[3]

            # Check if the pod is in the "CrashLoopBackOff" state
            if "CrashLoopBackOff" in pod_status:
                all_pods_stable = False
                print(f"Pod {pod_name} is in CrashLoopBackOff. Describing the pod...")

                # Describe the pod that is in CrashLoopBackOff
                describe_result = subprocess.run(
                    ['kubectl', 'describe', 'pod', pod_name, '-n', namespace],
                    check=True, capture_output=True, text=True
                )
                print(describe_result.stdout)
            else:
                stable_pods += 1

        if all_pods_stable and total_pods == stable_pods:
            print(f"All {total_pods} pods in namespace '{namespace}' are stable.")
            return True
        else:
            print(f"Pods not stable yet... ({stable_pods}/{total_pods})")
            return False

    except subprocess.CalledProcessError as e:
        print(f"Failed to check pods in namespace '{namespace}': {e}")
        return False
    
def destroy_cluster():
    terraform_dir = os.path.join("terraform-test-clusters", "EKS")

    print("Destroying Terraform-managed infrastructure...")
    run_command('terraform destroy -auto-approve', terraform_dir)
    print("Infrastructure destroyed successfully.")



def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Deploy Kubescape with optional Helm parameters")
    parser.add_argument('-kdr', action='store_true', help="Enable KDR capabilities")
    parser.add_argument('-nodes', type=int, default=2, help="Number of nodes (default is 2)")
    parser.add_argument('-account', type=str, required=True, help="Account ID")
    parser.add_argument('-accessKey', type=str, required=True, help="Access key")
    parser.add_argument('-destroy', action='store_true', help="Destroy the Terraform-managed infrastructure")
    parser.add_argument('-skip-cluster', action='store_true', help="Skip cluster creation and connection")
    parser.add_argument('-version', type=str, help="Specify the Helm chart version for Kubescape")

    args = parser.parse_args()
    
    terraform_dir = os.path.join("terraform-test-clusters", "EKS")
    
    if args.destroy:
        destroy_cluster()
        return  
    
    # Step 1: Create cluster and connect to it, unless --skip-cluster is used
    if not args.skip_cluster:
        node_count = setup_cluster(node_count=args.nodes)
        # Extract region and cluster name from Terraform outputs
        region = subprocess.run(['terraform', 'output', '-raw', 'region'], check=True, capture_output=True, text=True, cwd = terraform_dir).stdout.strip()
        cluster_name = subprocess.run(['terraform', 'output', '-raw', 'cluster_name'], check=True, capture_output=True, text=True, cwd = terraform_dir).stdout.strip()

        # Step 2: Connect to the EKS cluster
        connect_to_eks_cluster(region, cluster_name, terraform_dir)
    else:
        # Use default node count if skipping cluster creation
        print("Skipping cluster creation and connection.")
        node_count = args.nodes
    
    # Deploy prometheus and microservices demo
    deploy_kube_prometheus_stack()
    namespaces = create_parallel_namespaces(node_count)
    apply_microservices_demo(namespaces)
    
    # Step 3: Deploy Kubescape using Helm
    deploy_kubescape(account=args.account, accessKey=args.accessKey, version=args.version, enable_kdr=args.kdr)

    # Step 4: Check if the cluster is ready by polling the node readiness
    check_cluster_ready()

    # Step 5: Check if any pods are in CrashLoopBackOff state
    print("Checking for pods in CrashLoopBackOff state...")
    check_crashloop_pods(namespace="kubescape") 

if __name__ == "__main__":
    main()
