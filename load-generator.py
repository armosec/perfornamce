import threading
import subprocess
import time
import random
import os
import logging
from kubernetes import client, config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('kubescape-load-gen')

# Global list to track deployed pods
DEPLOYED_PODS = []

# Number of worker instances
FILE_WORKERS = int(os.getenv("FILE_WORKERS", "10"))
PROCESS_WORKERS = int(os.getenv("PROCESS_WORKERS", "10"))
DNS_WORKERS = int(os.getenv("DNS_WORKERS", "10"))

# List of vulnerable images to deploy
VULNERABLE_IMAGES = [
    "vulnerables/web-dvwa:latest",
    "bkimminich/juice-shop:latest",
    "webgoat/webgoat-8.0:latest",
    "gitlab/gitlab-ce:13.9.3-ce.0",
    "mongo:4.0",
    "jenkins:2.60.3",
    "tomcat:8.5.30",
]

# Load Kubernetes config
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

# Namespaces that should NOT be deleted
EXCLUDED_NAMESPACES = {"kube-system", "monitoring", "kubescape", "default"}

def get_all_nodes():
    """Returns a list of all node names."""
    try:
        nodes = v1.list_node().items
        return [node.metadata.name for node in nodes]
    except Exception as e:
        print(f"Error retrieving nodes: {e}")
        return []

def delete_namespaces_from_node(node_name, namespaces_to_delete):
    """Deletes up to `namespaces_to_delete` namespaces from the given node."""
    try:
        # Get all pods on this node
        pods = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}").items

        # Find non-excluded namespaces on this node
        namespaces = list({pod.metadata.namespace for pod in pods if pod.metadata.namespace not in EXCLUDED_NAMESPACES})

        if not namespaces:
            print(f"No deletable namespaces found on {node_name}, skipping...")
            return

        # Determine how many namespaces to delete (either the given limit or total available)
        delete_count = min(namespaces_to_delete, len(namespaces))

        # Select random namespaces to delete
        namespaces_to_delete = random.sample(namespaces, delete_count)

        for namespace in namespaces_to_delete:
            try:
                print(f"Deleting namespace {namespace} from node {node_name}")
                v1.delete_namespace(namespace)
                print(f"Namespace {namespace} deleted successfully!")
            except Exception as e:
                print(f"Error deleting namespace {namespace}: {e}")

    except Exception as e:
        print(f"Error deleting namespaces from {node_name}: {e}")

def delete_namespaces_across_nodes(namespaces_to_delete=2):
    """Finds all nodes and deletes `namespaces_to_delete` per node in parallel."""
    try:
        node_names = get_all_nodes()

        # Start threads for each node
        threads = [
            threading.Thread(target=delete_namespaces_from_node, args=(node, namespaces_to_delete))
            for node in node_names
        ]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

    except Exception as e:
        print(f"Error retrieving nodes: {e}")
        
# Create a dedicated namespace for the test
def get_next_namespace_number(base_name="new-load"):
    """Finds the next available namespace number."""
    existing_namespaces = [ns.metadata.name for ns in v1.list_namespace().items]
    
    # Find the highest existing new-load-* number
    next_number = 1
    while f"{base_name}-{next_number}" in existing_namespaces:
        next_number += 1

    return f"{base_name}-{next_number}"

def create_namespace():
    """Creates a new namespace with an incremental number."""
    unique_name = get_next_namespace_number()

    try:
        ns_metadata = client.V1ObjectMeta(name=unique_name)
        ns_body = client.V1Namespace(metadata=ns_metadata)
        v1.create_namespace(ns_body)
        print(f"Namespace {unique_name} created successfully!")
        return unique_name  # Return the name if needed
    except Exception as e:
        print(f"Error creating namespace {unique_name}: {e}")
        return None


# Get all nodes
def get_all_nodes():
    try:
        nodes = v1.list_node()
        return [node.metadata.name for node in nodes.items]
    except Exception as e:
        logger.error(f"Error getting nodes: {e}")
        return []

# Generate a unique deployment name based on the image name
def generate_deployment_name(image):
    image_name = image.split("/")[-1].replace(":", "-")  # Extract and format image name
    random_suffix = ''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=5))
    return f"vuln-{image_name}-{random_suffix}"

# Run file operations on deployed pods
def file_operations_worker(namespace):
    while True:
        for pod in DEPLOYED_PODS:
            logger.info(f"Running file operations on {pod} in namespace {namespace}")
            subprocess.run(
                ["kubectl", "exec", "-n", namespace, pod, "--", "sh", "-c", "touch /tmp/testfile && rm /tmp/testfile"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        time.sleep(10)

# Run process operations on deployed pods
def process_operations_worker(namespace):
    while True:
        for pod in DEPLOYED_PODS:
            logger.info(f"Running process operations on {pod} in namespace {namespace}")
            subprocess.run(
                ["kubectl", "exec", "-n", namespace, pod, "--", "sh", "-c", "ps aux"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        time.sleep(10)

# Run DNS operations on deployed pods
def dns_operations_worker(namespace):
    while True:
        for pod in DEPLOYED_PODS:
            logger.info(f"Running DNS operations on {pod} in namespace {namespace}")
            subprocess.run(
                ["kubectl", "exec", "-n", namespace, pod, "--", "sh", "-c", "nslookup google.com"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        time.sleep(10)

def deploy_vulnerable_images_as_daemonsets(namespace):
    """Deploys images in the dynamically set namespace."""
    if not namespace:
        logger.error("Namespace is not set! Exiting deployment.")
        return
    
    try:
        for image in VULNERABLE_IMAGES:
            daemonset_name = generate_deployment_name(image)
            logger.info(f"Deploying {image} as DaemonSet {daemonset_name} in namespace {namespace}")

            daemonset = client.V1DaemonSet(
                metadata=client.V1ObjectMeta(name=daemonset_name),
                spec=client.V1DaemonSetSpec(
                    selector=client.V1LabelSelector(
                        match_labels={"app": daemonset_name}
                    ),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={"app": daemonset_name}),
                        spec=client.V1PodSpec(
                            containers=[
                                client.V1Container(
                                    name="main-container",
                                    image=image,
                                    ports=[client.V1ContainerPort(container_port=80)]
                                )
                            ]
                        )
                    )
                )
            )

            apps_v1.create_namespaced_daemon_set(namespace=namespace, body=daemonset)
            logger.info(f"Deployed DaemonSet {daemonset_name}")
            
            # Get all pods from this DaemonSet
            time.sleep(10)  # Give some time for pods to be created
            pods = v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={daemonset_name}"
            )
            
            for pod in pods.items:
                DEPLOYED_PODS.append(pod.metadata.name)
                logger.info(f"Added pod {pod.metadata.name} to tracking list")

    except Exception as e:
        logger.error(f"Error deploying DaemonSets: {e}")

# Worker to deploy all images in a balanced way
def deployment_worker():
    delete_namespaces_across_nodes(namespaces_to_delete=2)
    
    # Dynamically assign namespace
    namespace = create_namespace()
    if not namespace:
        logger.error("Failed to create a namespace. Exiting...")
        return

    time.sleep(10)  # Ensure namespace is ready before deployment

    deploy_vulnerable_images_as_daemonsets(namespace)  # Pass namespace as an argument

    # Start workers in parallel with namespace argument
    for _ in range(FILE_WORKERS):
        threading.Thread(target=file_operations_worker, args=(namespace,), daemon=True).start()
    for _ in range(PROCESS_WORKERS):
        threading.Thread(target=process_operations_worker, args=(namespace,), daemon=True).start()
    for _ in range(DNS_WORKERS):
        threading.Thread(target=dns_operations_worker, args=(namespace,), daemon=True).start()

# Start workers
def main():
    deployment_thread = threading.Thread(target=deployment_worker, daemon=True)
    deployment_thread.start()
    deployment_thread.join()
    logger.info("All deployments completed and operations executed. Script exiting.")

if __name__ == "__main__":
    main()
