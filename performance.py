import os
import time
import yaml
import json
import requests
import argparse
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging


NODE_SIZES = {
    "s-2vcpu-2gb": {"vcpu": 2, "memory_gb": 2},
    "s-4vcpu-8gb": {"vcpu": 4, "memory_gb": 8},
    "s-8vcpu-16gb": {"vcpu": 8, "memory_gb": 16},
    "c2-16vcpu-32gb-intel": {"vcpu": 16, "memory_gb": 32},
    "c2-32vcpu-64gb-intel": {"vcpu": 32, "memory_gb": 64},
    "c2-48vcpu-96gb-intel": {"vcpu": 48, "memory_gb": 96}
}

DEFAULT_NODE_SIZE = "s-4vcpu-16gb"
DEFAULT_NODE_COUNT = 4

def setup_logging():
    # Get the directory where the script is running
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Create log file in the same directory
    log_file = os.path.join(script_dir, "config.log")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Keep console output too
        ]
    )
    return logging.getLogger()

logger = setup_logging()

def log_and_print(message):
    print(message)  # Console
    logger.info(message)  # Log file

def run_command(command, cwd=None):
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, shell=True, cwd=cwd)
        print(result.stdout)
        return result.stdout.strip()  # Return the output and strip whitespace
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
            f"-n monitoring --create-namespace --timeout 10m0s"
        )

        # Run the command
        print("Deploying kube-prometheus-stack using Helm...")
        run_command(helm_command)
        print("kube-prometheus-stack deployed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to deploy kube-prometheus-stack with exit code {e.returncode}")
        print(f"Error output:\n{e.stderr}")
        exit(1)

def deploy_pyroscope():
    try:
        # Define paths relative to the script's directory
        values_file = "./Monitoring/pyroscope/dev-env-values.yaml"
        chart_path = "./Monitoring/pyroscope"

        # Construct the Helm command
        helm_command = (
            f"helm upgrade --install pyroscope "
            f"-f {values_file} "
            f"{chart_path} "
            f"-n monitoring --create-namespace"
        )
        # Run the command
        print("Deploying Pyroscope using Helm...")
        run_command(helm_command)
        print("Pyroscope deployed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to deploy Pyroscope with exit code {e.returncode}")
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

def create_parallel_namespaces(node_size, node_count, skip_cluster=False):
    try:
        node_size = NODE_SIZES[node_size]
        vcpu = node_size["vcpu"]
        # The original calculation assumes 4cpu and 8Gb memory so let's adjust for that
        multiplier = vcpu / 4
        # Adjust the node count for the new node size
        node_count = int(node_count * multiplier)

        if skip_cluster:
            # Get the number of nodes in the cluster
            result = subprocess.run(
                ['kubectl', 'get', 'nodes', '--no-headers'],
                check=True, capture_output=True, text=True
            )
            total_nodes = len(result.stdout.splitlines())
            num_namespaces = (total_nodes - 2) * 2
        else:
            # Calculate the number of namespaces to create
            num_namespaces = (node_count - 2) * 2

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

def apply_microservices_demo(namespaces):
    microservices_demo_path = os.path.join("microservices-demo", "release", "kubernetes-manifests.yaml")
    for namespace in namespaces:
        print(f"Applying microservices-demo to namespace {namespace}...")
        try:
            run_command(f'kubectl apply -f {microservices_demo_path} -n {namespace}')
            print(f"Successfully applied microservices-demo to namespace {namespace}.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to apply microservices-demo to namespace {namespace}: {e}")
            exit(1)

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

def adjust_load_simulator_cpu_resources(yaml_path, cpu_load_ms, number_parallel_cpus):
        import yaml
        import tempfile

        # Load the DaemonSet YAML file into a Python variable
        with open(yaml_path, 'r') as f:
            daemonset_yaml = list(yaml.safe_load_all(f))

        # Find the DaemonSet spec in the loaded YAML (in case it's a multi-doc YAML)
        for doc in daemonset_yaml:
            if doc and doc.get('kind') == 'DaemonSet':
                ds_spec = doc
                break
        else:
            raise Exception("DaemonSet not found in load simulator YAML")

        # Calculate CPU requests/limits based on cpuLoadMs and numberParallelCPUs
        total_cpu_millicores = int(cpu_load_ms * number_parallel_cpus)

        # Set the resources in the DaemonSet spec
        containers = ds_spec['spec']['template']['spec']['containers']
        for container in containers:
            if container.get('name') == 'load-simulator':
                if 'resources' not in container:
                    container['resources'] = {}
                container['resources']['requests'] = {
                    'cpu': f"{total_cpu_millicores}m",
                    'memory': '128Mi'
                }
                container['resources']['limits'] = {
                    'cpu': f"{total_cpu_millicores}m",
                    'memory': '512Mi'
                }

        # Write the modified DaemonSet YAML to a temp file for kubectl apply
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.yaml') as tmpf:
            yaml.dump_all(daemonset_yaml, tmpf)
            return tmpf.name

def apply_load_simulator(node_size, node_count):
    print(f"Applying load simulator to {node_count} nodes of size {node_size}...")
    load_simulator_path = os.path.join("load-simulator", "daemonset.yaml")



    run_command(f'kubectl create namespace load-simulator')

    # Load simulator parameters
    exec_rate = 10
    hardlink_rate = 10
    http_rate = 10
    network_rate = 10
    open_rate = 100
    symlink_rate = 10
    dns_rate = 2

    # Get the number of vCPUs in the node size
    node_size_vcpu = 4
    if node_size in NODE_SIZES:
        node_size_vcpu = NODE_SIZES[node_size]["vcpu"]
    else:
        print(f"WARNING: Node size {node_size} not found in NODE_SIZES, defaulting to 4 vCPUs")
        node_size_vcpu = 4

    # 50% cpu load
    cpu_load_ms = 500

    # Create the config map
    config_content = f'''cpuLoadMs: {cpu_load_ms}
numberParallelCPUs: {node_size_vcpu}
dnsRate: {dns_rate}
execRate: {exec_rate}
hardlinkRate: {hardlink_rate}
httpRate: {http_rate}
networkRate: {network_rate}
openRate: {open_rate}
symlinkRate: {symlink_rate}'''

    # Create configmap using --from-file instead of --from-literal
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.yaml') as tmpf:
        tmpf.write(config_content)
        config_file = tmpf.name

    run_command(f'kubectl create configmap config --from-file=config.yaml={config_file} -n load-simulator')
    os.unlink(config_file)  # Clean up temp file

    # Use the function to adjust the DaemonSet YAML before applying
    load_simulator_path = adjust_load_simulator_cpu_resources(
        load_simulator_path,
        cpu_load_ms=cpu_load_ms,
        number_parallel_cpus=node_size_vcpu
    )

    run_command(f'kubectl apply -f {load_simulator_path} -n load-simulator')

    # Wait for the load simulator to be ready
    print("Waiting for the load simulator to be ready...")
    run_command(f'kubectl wait --for=condition=ready pod -l app=load-simulator -n load-simulator --timeout=300s')
    print("Load simulator deployed successfully.")



# Step 2: Deploy Kubescape using Helm
def deploy_kubescape(
    account: str,
    accessKey: str,
    version: str = None,
    enable_kdr: bool = False,
    additional_helm_command: str = None,
    storage_image_tag: str = None,
    node_agent_image_tag: str = None,
    private_node_agent: str = None,
    released_private_node_agent: str = None,
    helm_git_branch: str = None,
    resource_config: dict = None,
    use_private_node_agent: bool = False,
    application_mode: str = 'microservices-demo'
):
    try:
        git_commit_hash = None  # Initialize git commit hash variable
        chart_location = None   # Initialize chart location

        if helm_git_branch:
            # Since we always expect a branch name, use the default Kubescape repo
            repo_url = "https://github.com/kubescape/helm-charts.git"
            branch_name = helm_git_branch
            log_and_print(f"Using default repo {repo_url} with branch {branch_name}")

            repo_name = repo_url.split('/')[-1].replace('.git', '')
            helm_chart_path = f"/tmp/{repo_name}"

            # Clean up existing directory if it exists
            if os.path.exists(helm_chart_path):
                log_and_print(f"Removing existing directory: {helm_chart_path}")
                run_command(f"rm -rf {helm_chart_path}")

            # Clone the repository without specifying a branch first
            clone_command = f"git clone {repo_url} {helm_chart_path}"
            log_and_print(f"Cloning repository with command: {clone_command}")
            run_command(clone_command)

            # Then checkout to the specified branch if provided
            if branch_name:
                checkout_command = f"git -C {helm_chart_path} checkout {branch_name}"
                log_and_print(f"Checking out branch: {checkout_command}")
                run_command(checkout_command)

            # Get the git commit hash after checkout for tracking purposes
            git_commit_hash = run_command(f"git -C {helm_chart_path} rev-parse HEAD").strip()
            log_and_print(f"Using Git commit hash: {git_commit_hash}")

            # Detect the correct chart path
            possible_chart_paths = [
                os.path.join(helm_chart_path, "kubescape-operator"),
                os.path.join(helm_chart_path, "charts", "kubescape-operator")
            ]

            for path in possible_chart_paths:
                if os.path.exists(path):
                    chart_location = path
                    log_and_print(f"Found chart at: {chart_location}")
                    break

            if not chart_location:
                error_msg = f"Error: Could not find the kubescape-operator chart in {helm_chart_path}"
                log_and_print(error_msg)
                raise Exception(error_msg)

            # Build dependencies for the chart
            log_and_print(f"Running 'helm dependency build' for {chart_location}...")
            run_command(f"helm dependency build {chart_location}")

        else:
            log_and_print("Using Kubescape Helm repository...")
            run_command('helm repo add kubescape https://kubescape.github.io/helm-charts/')
            run_command('helm repo update')
            chart_location = "kubescape/kubescape-operator"

        print("Deploying Kubescape Operator...")
        cluster_context = subprocess.run(['kubectl', 'config', 'current-context'], check=True, capture_output=True, text=True).stdout.strip()

        # Build base helm command
        helm_command = (
            f'helm upgrade --install kubescape {chart_location} '
            f'-n kubescape --create-namespace '
            f'--set clusterName={cluster_context} '
            f'--set account={account} '
            f'--set accessKey={accessKey} '
            f'--set server=api.armosec.io '
            f'--set nodeAgent.config.maxLearningPeriod=60m '
            f'--set nodeAgent.env[0].name=PYROSCOPE_SERVER_SVC '
            f'--set nodeAgent.env[0].value=http://pyroscope-distributor.monitoring.svc.cluster.local.:4040 '
            f'--set storage.env[0].name=PYROSCOPE_SERVER_SVC '
            f'--set storage.env[0].value=http://pyroscope-distributor.monitoring.svc.cluster.local.:4040'
        )

        # Add optional parameters
        if version and not helm_git_branch:  # Only use version if not using Git branch
            helm_command += f' --version {version}'

        if storage_image_tag:
            repository = "quay.io/kubescape/storage"
            if storage_image_tag.count("/") > 0:
                # this is a full image tag, so we need to split it
                tag = storage_image_tag.split(":")[-1]
                repository = ':'.join(storage_image_tag.split(":")[:-1])
                helm_command += f' --set storage.image.tag={tag} --set storage.image.repository={repository}'
            else:
                helm_command += f' --set storage.image.tag={storage_image_tag} --set storage.image.repository={repository}'

        if node_agent_image_tag:
            repository = "quay.io/kubescape/node-agent"
            if node_agent_image_tag.count("/") > 0:
                # this is a full image tag, so we need to split it
                tag = node_agent_image_tag.split(":")[-1]
                repository = ':'.join(node_agent_image_tag.split(":")[:-1])
                helm_command += f' --set nodeAgent.image.tag={tag} --set nodeAgent.image.repository={repository}'
            else:
                helm_command += f' --set nodeAgent.image.tag={node_agent_image_tag} --set nodeAgent.image.repository={repository}'


        # Add KDR-specific parameters if enabled
        if enable_kdr:
            additional_params = (
                ' --set alertCRD.installDefault=true '
                ' --set capabilities.manageWorkloads=enable '
                ' --set capabilities.nodeProfileService=enable '
                ' --set capabilities.runtimeDetection=enable '
                ' --set imagePullSecret.password=Q5UMRCFPRAHAIRWAYTOP7P4PK9ZNV2H26JFTB70CMNZ2KG1NHGPYXK6PNPNC677E '
                ' --set imagePullSecret.server=quay.io '
                ' --set imagePullSecret.username=armosec+armosec_ro '
                ' --set imagePullSecrets=armosec-readonly '
            )

            # Handle private node agent configuration only if use_private_node_agent is specified
            if use_private_node_agent:
                if private_node_agent:
                    additional_params += f' --set nodeAgent.image.tag={private_node_agent} --set nodeAgent.image.repository=quay.io/armosec/node-agent'
                elif released_private_node_agent:
                    additional_params += f' --set nodeAgent.image.tag={released_private_node_agent} --set nodeAgent.image.repository=quay.io/armosec/node-agent'
                else:
                    error_msg = "ERROR: -use-private-node-agent specified but no private node agent version available (neither -private-node-agent nor released_private_node_agent)."
                    print(error_msg)
                    raise Exception(error_msg)
            elif node_agent_image_tag:
                pass # a node agent tag was specified in the args - don't override it

            helm_command += ' ' + additional_params

        # Add any additional helm parameters
        if additional_helm_command:
            log_and_print(f"Appending additional Helm parameters: {additional_helm_command}")
            helm_command += f" {additional_helm_command}"

        # Add resource configuration if provided
        if resource_config:
            log_and_print("Adding resource configuration to Helm command...")
            for component, resources in resource_config.items():
                if component == "node-agent":
                    helm_command += f' --set nodeAgent.resources.requests.cpu={resources["CPU"]}'
                    helm_command += f' --set nodeAgent.resources.requests.memory={resources["Memory"]}Mi'
                    helm_command += f' --set nodeAgent.resources.limits.cpu={resources["CPU"]}'
                    helm_command += f' --set nodeAgent.resources.limits.memory={resources["Memory"]}Mi'
                elif component == "storage":
                    helm_command += f' --set storage.resources.requests.memory={resources["Memory"]}Mi'
                    helm_command += f' --set storage.resources.limits.cpu={resources["CPU"]}'
                    helm_command += f' --set storage.resources.limits.memory={resources["Memory"]}Mi'
                elif component == "kubevuln":
                    helm_command += f' --set kubevuln.resources.limits.cpu={resources["CPU"]}'
                    helm_command += f' --set kubevuln.resources.limits.memory={resources["Memory"]}Mi'

        # Enable prometheus metrics in node agent
        helm_command += ' --set configurations.prometheusAnnotations=enable'
        helm_command += ' --set nodeAgent.config.prometheusExporter=enable'
        helm_command += ' --set nodeAgent.serviceMonitor.enabled=true'

        # Disable HTTP exporter for load-simulator mode to prevent alerts to Armo backend
        if application_mode == 'load-simulator':
            log_and_print("Load-simulator mode detected: disabling node-agent HTTP exporter to prevent alerts to Armo backend")
            helm_command += ' --set nodeAgent.config.httpExporterConfig=null'

        log_and_print(f"Final Helm command: {helm_command}")
        run_command(helm_command)

        print("Waiting for operator to deploy - 30 sec")
        time.sleep(30)  # Wait for the operator to deploy
        print("Kubescape Operator deployed successfully.")

    except Exception as e:
        log_and_print(f"Error deploying Kubescape: {str(e)}")
        raise

def get_node_agent_tag_from_git():
    """
    Fetch nodeAgent.image.tag from values.yaml in the GitHub repository.
    """
    repo_url = "https://raw.githubusercontent.com/armosec/kubernetes-deployment/master/Helm/cyberarmor-be-apps/charts/dashboardBEFrontegg/values.yaml"
    github_token = os.getenv("PERFO_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")

    headers = {"Authorization": f"token {github_token}"} if github_token else {}

    try:
        response = requests.get(repo_url, headers=headers)
        response.raise_for_status()  # Raise error if request fails

        # Parse the YAML content directly from response
        data = yaml.safe_load(response.text)
        tag = data.get('dashboardBE', {}).get('config', {}).get('KubescapeHelmCommandRuntimeThreatDetectionFeatureValues', {}).get('nodeAgent.image.tag', 'No tag found')

        if tag:
            print(f"Found nodeAgent.image.tag in GitHub: {tag}")
            return tag
        else:
            print("Error: nodeAgent.image.tag not found in GitHub values.yaml.")
            return None
    except Exception as e:
        print(f"Error fetching values.yaml from GitHub: {e}")
        exit(1)
        return None

def check_and_fix_node_agent_env():
    """
    Checks if the nodeAgent DaemonSet has the required Pyroscope environment variables.
    If not, it adds them using a kubectl patch command.
    """
    # Step 1: Get the nodeAgent DaemonSet
    try:
        print("Checking nodeAgent DaemonSet for Pyroscope environment variables...")
        result = subprocess.run(
            ['kubectl', 'get', 'daemonset', 'node-agent', '-n', 'kubescape', '-o', 'json'],
            check=True, capture_output=True, text=True
        )

        ds_json = json.loads(result.stdout)

        # Step 2: Check if the environment variables exist
        env_vars = ds_json.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [{}])[0].get('env', [])

        has_pyroscope_server = False
        for env in env_vars:
            if env.get('name') == 'PYROSCOPE_SERVER_SVC':
                has_pyroscope_server = True
                break

        # Step 3: If environment variables don't exist, patch the DaemonSet
        if not has_pyroscope_server:
            print("Pyroscope environment variables not found in nodeAgent. Adding them...")

            # Create the patch JSON
            patch = {
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "node-agent",
                                    "env": [
                                        {
                                            "name": "PYROSCOPE_SERVER_SVC",
                                            "value": "http://pyroscope-distributor.monitoring.svc.cluster.local.:4040"
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }

            # Convert patch to JSON string
            patch_json = json.dumps(patch)

            # Apply the patch
            patch_cmd = [
                'kubectl', 'patch', 'daemonset', 'node-agent',
                '-n', 'kubescape', '--type', 'strategic', '-p', patch_json
            ]

            subprocess.run(patch_cmd, check=True)
            print("Successfully patched nodeAgent DaemonSet with Pyroscope environment variables.")

            # Restart the DaemonSet pods to apply changes
            print("Restarting nodeAgent pods to apply changes...")
            subprocess.run([
                'kubectl', 'rollout', 'restart', 'daemonset/node-agent', '-n', 'kubescape'
            ], check=True)

            return True
        else:
            print("Pyroscope environment variables already set in nodeAgent DaemonSet.")
            return False

    except subprocess.CalledProcessError as e:
        print(f"Error checking nodeAgent DaemonSet: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False

def calculate_resources(node_size, node_count, enable_kdr=False, runtime_detection=True, node_sbom_generation=False, direct_io_storage=False, estimated_workloads=None):
    """Calculates resource requests and limits based on node size, count, and estimated cluster resources."""

    node_size = node_size or DEFAULT_NODE_SIZE
    node_count = node_count or DEFAULT_NODE_COUNT
    log_and_print(f"{node_count} nodes of size '{node_size}'")

    if node_size not in NODE_SIZES:
        print(f"Warning: Unknown NODE_SIZE '{node_size}'. Using default '{DEFAULT_NODE_SIZE}'.")
        node_size = DEFAULT_NODE_SIZE

    vcpu_per_node = NODE_SIZES[node_size]["vcpu"]
    memory_per_node_gb = NODE_SIZES[node_size]["memory_gb"]

    # **Step 1: Apply 50% Increase First If `enable_kdr` is True**
    if enable_kdr:
        vcpu_per_node = int(vcpu_per_node * 1.5)
        memory_per_node_gb = int(memory_per_node_gb * 1.5)

    # **Step 2: Compute Resource Allocations Normally**
    total_vcpu = vcpu_per_node * node_count
    total_memory_gb = memory_per_node_gb * node_count

    print(f"\nCluster Resources - Nodes: {node_count}, Total vCPU: {total_vcpu}, Total Memory: {total_memory_gb}GB")

    # Estimate total resources based on node count and application mode
    if estimated_workloads is None:
        # Estimate based on node count: microservices-demo creates (node_count-2)*2 namespaces
        # Each namespace has ~10-15 pods, so estimate total workloads
        estimated_workloads = (node_count - 2) * 2 * 12  # 12 pods per namespace average

    total_resources = estimated_workloads
    log_and_print(f"Estimated total workloads: {total_resources}")

    # **Node-Agent Calculation (Matching Guidelines)**
    cpu_adjustment = 0.75 if not runtime_detection else 1.0  # Reduce by 25% if runtimeDetection is off
    memory_adjustment = 1.0 + (0.2 if node_sbom_generation else 0)  # Add 200MB if nodeSbomGeneration is on

    node_agent_cpu_request = round(0.025 * vcpu_per_node * cpu_adjustment, 3)
    node_agent_cpu_limit = round(0.10 * vcpu_per_node * cpu_adjustment, 3)
    node_agent_memory_request = round(0.025 * memory_per_node_gb * 1024 * memory_adjustment, 2)
    node_agent_memory_limit = round(0.10 * memory_per_node_gb * 1024 * memory_adjustment, 2)

    # **Storage Calculation**
    storage_memory_request = round(0.2 * total_resources, 2)
    storage_memory_limit = round(0.8 * total_resources, 2)

    if direct_io_storage:
        storage_memory_request /= 2
        storage_memory_limit /= 2

    storage_cpu_limit = round(storage_memory_limit / 8000, 3)  # Scale CPU based on memory

    # **KubeVuln Calculation**
    largest_image_size_mb = 1000  # Assume 1GB image size
    kubevuln_memory_limit = largest_image_size_mb + 400
    kubevuln_cpu_limit = round(0.1 * total_vcpu, 3)

    config = {
        "node-agent": {
            "Memory": node_agent_memory_limit,
            "CPU": node_agent_cpu_limit
        },
        "storage": {
            "Memory": storage_memory_limit,
            "CPU": storage_cpu_limit
        },
        "kubevuln": {
            "Memory": kubevuln_memory_limit,
            "CPU": kubevuln_cpu_limit
        }
    }

    # Save calculated thresholds
    config_json_path = "/tmp/pod_thresholds.json"
    with open(config_json_path, "w") as f:
        json.dump(config, f, indent=2)

    # **Apply them as a Kubernetes ConfigMap**
    try:
        subprocess.run(
            f"kubectl create configmap pod-thresholds --from-file=pod_thresholds.json={config_json_path} "
            f"-n default --dry-run=client -o yaml | kubectl apply -f -",
            shell=True, check=True
        )
        print("ConfigMap `pod-thresholds` updated successfully!")

    except subprocess.CalledProcessError as e:
        print(f"Failed to create ConfigMap: {e}")

    log_and_print("\n Computed Resource Allocations:")
    for pod, resources in config.items():
        log_and_print(f"{pod} -> CPU: {resources['CPU']} cores, Memory: {resources['Memory']} MiB")

    return config

def update_kubescape_helm(node_size, node_count, helm_git_branch=None):
    """
    DEPRECATED: Updates the Kubescape deployment using Helm based on cluster specifications.

    This function is deprecated in favor of calculating resources upfront and using
    a single Helm installation in deploy_kubescape().
    """
    print("Updating Kubescape configuration...")

    # Step 1: Calculate optimal resources
    config = calculate_resources(node_size, node_count)

    # Step 2: Save the configuration
    with open("kubescape-autoscale.yaml", "w") as file:
        yaml.dump(config, file, default_flow_style=False)

    # Step 3: Handle ks-cloud-config ConfigMap issue
    print("Checking for existing ks-cloud-config ConfigMap...")

    result = subprocess.run(
        ['kubectl', 'get', 'configmap', 'ks-cloud-config', '-n', 'kubescape'],
        capture_output=True, text=True)

    if result.returncode == 0:  # ConfigMap exists
        print("ks-cloud-config ConfigMap found. Deleting it to avoid Helm upgrade failure...")
        subprocess.run(['kubectl', 'delete', 'configmap', 'ks-cloud-config', '-n', 'kubescape'], check=True)
        print("ks-cloud-config ConfigMap deleted successfully.")

    else:
        print("No ks-cloud-config ConfigMap found. Proceeding with Helm upgrade...")

    # Step 4: Determine chart location based on git branch
    if helm_git_branch:
        # Since we always expect a branch name, use the default Kubescape repo
        repo_url = "https://github.com/kubescape/helm-charts.git"
        branch_name = helm_git_branch
        log_and_print(f"Using default repo {repo_url} with branch {branch_name}")

        repo_name = repo_url.split('/')[-1].replace('.git', '')
        helm_chart_path = f"/tmp/{repo_name}"

        # Check if repo is already cloned, if not - clone it
        if not os.path.exists(helm_chart_path):
            clone_command = f"git clone {repo_url} {helm_chart_path}"
            log_and_print(f"Cloning repository with command: {clone_command}")
            run_command(clone_command)

        # Make sure we're on the right branch
        checkout_command = f"git -C {helm_chart_path} checkout {branch_name}"
        log_and_print(f"Checking out branch: {checkout_command}")
        run_command(checkout_command)

        # Detect the correct chart path
        possible_chart_paths = [
            os.path.join(helm_chart_path, "kubescape-operator"),
            os.path.join(helm_chart_path, "charts", "kubescape-operator")
        ]

        chart_location = None
        for path in possible_chart_paths:
            if os.path.exists(path):
                chart_location = path
                log_and_print(f"Found chart at: {chart_location}")
                break

        if not chart_location:
            error_msg = f"Error: Could not find the kubescape-operator chart in {helm_chart_path}"
            log_and_print(error_msg)
            raise Exception(error_msg)

        # Build dependencies for the chart
        log_and_print(f"Running 'helm dependency build' for {chart_location}...")
        run_command(f"helm dependency build {chart_location}")

        # Step 5: Apply the update via Helm with the git branch chart
        helm_command = (
            f"helm upgrade --install kubescape {chart_location} "
            f"-n kubescape -f kubescape-autoscale.yaml"
        )
    else:
        # Use standard chart from Helm repo
        # Ensure Helm Repo Exists
        print("Ensuring Kubescape Helm repository is added...")

        helm_repo_check = subprocess.run(
            "helm repo list | grep kubescape",
            shell=True,
            capture_output=True,
            text=True
        )

        if helm_repo_check.returncode != 0:
            print("Kubescape Helm repository not found. Adding it now...")
            run_command('helm repo add kubescape https://kubescape.github.io/helm-charts/')

        # Always update Helm repositories
        run_command('helm repo update')

        # Apply the update via standard Helm repo
        helm_command = (
            "helm upgrade --install kubescape kubescape/kubescape-operator "
            "-n kubescape -f kubescape-autoscale.yaml"
        )

    # Run the prepared helm command
    run_command(helm_command)
    print("Kubescape updated with optimized resource allocation.")


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

def check_component_versions():
    """
    Check and display the versions of all Kubescape components deployed in the cluster.
    """
    try:
        # Run the exact command you provided
        cmd = "kubectl get pods -n kubescape -o jsonpath='{range .items[*]}{.metadata.name}{\" -> \"}{.spec.containers[*].image}{\"\\n\"}{end}' | awk -F'/' '{print $NF}' | awk -F':' '{if ($2 ~ /^v/) print $1\": \"$2; else print $1\": v\"$2}' | sort -u"

        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)

        # Print the result directly
        log_and_print("\nKubescape Component Versions:")
        if result.stdout:
            log_and_print(result.stdout)
        else:
            print("No components found or all components are pending")

    except subprocess.CalledProcessError as e:
        print(f"Error checking component versions: {e}")
        print(f"Error output:\n{e.stderr}")

def destroy_cluster():
    terraform_dir = os.path.join("terraform-test-clusters", "EKS")

    print("Destroying Terraform-managed infrastructure...")
    run_command('terraform destroy -auto-approve', terraform_dir)
    print("Infrastructure destroyed successfully.")



def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Deploy Kubescape with optional Helm parameters")
    parser.add_argument('-kdr', action='store_true', help="Enable KDR capabilities")
    parser.add_argument('-nodes', type=int, default=DEFAULT_NODE_COUNT, help="Number of nodes (default is 4)")
    parser.add_argument('-node_size', type=str, default=DEFAULT_NODE_SIZE, help="Node type (default is s-4vcpu-16gb)")
    parser.add_argument('-account', type=str, required=True, help="Account ID")
    parser.add_argument('-accessKey', type=str, required=True, help="Access key")
    parser.add_argument('-duration', type=int, default=4, help="Duration time in hours (default is 4)")
    parser.add_argument('-destroy', action='store_true', help="Destroy the Terraform-managed infrastructure")
    parser.add_argument('-skip-cluster', action='store_true', help="Skip cluster creation and connection")
    parser.add_argument('-version', type=str, help="Specify the Helm chart version for Kubescape")
    parser.add_argument('-additional-helm-command', type=str, help="Additional helm command")
    parser.add_argument('-storage-version', type=str, help="Specify the storage image version")
    parser.add_argument('-node-agent-version', type=str, help="Specify the node agent image version")
    parser.add_argument('-private-node-agent', type=str, help="Specify the private node agent version")
    parser.add_argument('-use-private-node-agent', action='store_true', help="Use private node agent image when KDR is enabled")
    parser.add_argument('-helm-git-branch', type=str, help="Git branch name or full repository URL for custom Helm chart")
    parser.add_argument('--application-mode', type=str, default='microservices-demo', choices=['microservices-demo', 'load-simulator'], help="Application mode (default is 'microservices-demo', other option is 'load-simulator')")


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
    deploy_pyroscope()

    # Calculate resources ahead of time for single Helm installation
    log_and_print("Calculating resource requirements...")
    resource_config = calculate_resources(
        node_size=args.node_size,
        node_count=node_count,
        enable_kdr=args.kdr
    )

    # Only fetch released_private_node_agent if use_private_node_agent is specified
    # This allows KDR to work with default Helm chart images unless explicitly requested
    released_private_node_agent = None
    if args.use_private_node_agent:
        released_private_node_agent = get_node_agent_tag_from_git()

    # Step 3: Deploy Kubescape using Helm with pre-calculated resources
    deploy_kubescape(
        account=args.account,
        accessKey=args.accessKey,
        version=args.version,
        enable_kdr=args.kdr,
        additional_helm_command=args.additional_helm_command,
        storage_image_tag=args.storage_version,
        node_agent_image_tag=args.node_agent_version,
        private_node_agent=args.private_node_agent,
        released_private_node_agent=released_private_node_agent,
        helm_git_branch=args.helm_git_branch,
        resource_config=resource_config,
        use_private_node_agent=args.use_private_node_agent,
        application_mode=args.application_mode
    )

    time.sleep(40)  # Wait for the operator to deploy
    if args.application_mode == 'microservices-demo':
        namespaces = create_parallel_namespaces(args.node_size,node_count)
        apply_microservices_demo(namespaces)
    elif args.application_mode == 'load-simulator':
        apply_load_simulator(node_size=args.node_size, node_count=node_count)

    # Step 4: Check if the cluster is ready by polling the node readiness
    check_cluster_ready()

    # Note: Resource optimization is now included in the initial Helm installation
    time.sleep(30)  # Wait for the operator
    print("Verifying nodeAgent Pyroscope environment variables...")

    if check_and_fix_node_agent_env():
        time.sleep(30)
        print("NodeAgent Pyroscope environment variables fixed successfully.")
    else:
        print("NodeAgent Pyroscope environment variables already set.")


    # Step 6: Check if any pods are in CrashLoopBackOff state
    print("Checking for pods in CrashLoopBackOff state...")
    check_crashloop_pods(namespace="kubescape")
    check_component_versions()

if __name__ == "__main__":
    main()
