import threading
import subprocess
import time
import random
import os
import logging
import signal
import sys
from kubernetes import client, config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('kubescape-load-gen')

# Global list to track deployed pods
DEPLOYED_PODS = []

# Global list to track created namespaces for cleanup
CREATED_NAMESPACES = []

# Counter to track when to clear the pods list
POD_CLEAR_COUNTER = 0
POD_CLEAR_INTERVAL = 5  # Clear pods list every 5 deployment cycles

# Global flag to stop worker threads
STOP_WORKERS = False

# List to track worker threads
WORKER_THREADS = []

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
EXCLUDED_NAMESPACES = {"kube-system", "monitoring", "kubescape", "default", "namespace-1", "namespace-2", "namespace-3", "namespace-4", "namespace-5", "namespace-6", "namespace-7", "namespace-8", "namespace-9"," namespace-10"}

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

def delete_namespaces_across_nodes(namespaces_to_delete=1):
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
        CREATED_NAMESPACES.append(unique_name) # Add to list for cleanup
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
        if STOP_WORKERS:
            logger.info("Stopping file operations worker.")
            break
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
        if STOP_WORKERS:
            logger.info("Stopping process operations worker.")
            break
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
        if STOP_WORKERS:
            logger.info("Stopping DNS operations worker.")
            break
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

def clear_pods_list():
    """Clear the global pods list to prevent memory accumulation."""
    global DEPLOYED_PODS, POD_CLEAR_COUNTER
    POD_CLEAR_COUNTER += 1

    if POD_CLEAR_COUNTER >= POD_CLEAR_INTERVAL:
        logger.info(f"Clearing pods list after {POD_CLEAR_COUNTER} deployment cycles")
        DEPLOYED_PODS.clear()
        POD_CLEAR_COUNTER = 0

# Worker to deploy all images in a balanced way
def deployment_worker():
    global POD_CLEAR_COUNTER

    delete_namespaces_across_nodes(namespaces_to_delete=1)

    # Clear pods list periodically
    clear_pods_list()

    # Dynamically assign namespace
    namespace = create_namespace()
    if not namespace:
        logger.error("Failed to create a namespace. Exiting...")
        return

    time.sleep(10)  # Ensure namespace is ready before deployment

    deploy_vulnerable_images_as_daemonsets(namespace)  # Pass namespace as an argument

    # Start workers in parallel with namespace argument
    for _ in range(FILE_WORKERS):
        thread = threading.Thread(target=file_operations_worker, args=(namespace,), daemon=True)
        thread.start()
        WORKER_THREADS.append(thread)
    for _ in range(PROCESS_WORKERS):
        thread = threading.Thread(target=process_operations_worker, args=(namespace,), daemon=True)
        thread.start()
        WORKER_THREADS.append(thread)
    for _ in range(DNS_WORKERS):
        thread = threading.Thread(target=dns_operations_worker, args=(namespace,), daemon=True)
        thread.start()
        WORKER_THREADS.append(thread)

def cleanup_resources():
    """Clean up all created resources."""
    logger.info("Starting cleanup of created resources...")

    for namespace in CREATED_NAMESPACES:
        try:
            logger.info(f"Cleaning up namespace: {namespace}")
            v1.delete_namespace(namespace)
            logger.info(f"Namespace {namespace} deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting namespace {namespace}: {e}")

    logger.info("Cleanup completed")

def signal_handler(signum, frame):
    """Handle interrupt signals to ensure cleanup."""
    logger.info(f"Received signal {signum}, starting cleanup...")
    global STOP_WORKERS
    STOP_WORKERS = True
    cleanup_resources()
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Start workers
def main():
    global STOP_WORKERS

    try:
        deployment_thread = threading.Thread(target=deployment_worker, daemon=True)
        deployment_thread.start()
        deployment_thread.join()
        logger.info("All deployments completed and operations executed.")
    finally:
        # Signal all worker threads to stop
        logger.info("Signaling worker threads to stop...")
        STOP_WORKERS = True

        # Wait for worker threads to finish
        logger.info("Waiting for worker threads to finish...")
        for thread in WORKER_THREADS:
            if thread.is_alive():
                thread.join(timeout=5)  # Wait up to 5 seconds for each thread

        # Clear the thread list
        WORKER_THREADS.clear()

        cleanup_resources()
        logger.info("Script exiting.")

if __name__ == "__main__":
    main()
