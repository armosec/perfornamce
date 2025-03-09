import threading
import subprocess
import time
import random
import os
import logging
import yaml
import concurrent.futures
from kubernetes import client, config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('kubescape-load-gen')

# Global list to track deployed pods
DEPLOYED_PODS = []
NAMESPACE = "new-load"

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

# Delete the last 2 created namespaces
def delete_last_two_namespaces():
    try:
        namespaces = v1.list_namespace().items
        namespace_names = [ns.metadata.name for ns in namespaces if ns.metadata.name.startswith("namespace-")]
        namespace_names.sort(reverse=True)  # Sort by name (assuming name ordering reflects creation order)
        
        namespaces_to_delete = namespace_names[:2]  # Select the last two namespaces
        
        for ns in namespaces_to_delete:
            logger.info(f"Deleting namespace: {ns}")
            v1.delete_namespace(name=ns)
            time.sleep(5)  # Small delay to allow deletion
    except Exception as e:
        logger.error(f"Error deleting namespaces: {e}")

# Create a dedicated namespace for the test
def create_namespace():
    try:
        ns_metadata = client.V1ObjectMeta(name=NAMESPACE)
        ns_body = client.V1Namespace(metadata=ns_metadata)
        v1.create_namespace(ns_body)
        logger.info(f"Namespace {NAMESPACE} created.")
    except Exception as e:
        logger.warning(f"Namespace {NAMESPACE} might already exist: {e}")

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
def file_operations_worker():
    while True:
        for pod in DEPLOYED_PODS:
            logger.info(f"Running file operations on {pod}")
            subprocess.run(["kubectl", "exec", "-n", NAMESPACE, pod, "--", "sh", "-c", "touch /tmp/testfile && rm /tmp/testfile"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10)

# Run process operations on deployed pods
def process_operations_worker():
    while True:
        for pod in DEPLOYED_PODS:
            logger.info(f"Running process operations on {pod}")
            subprocess.run(["kubectl", "exec", "-n", NAMESPACE, pod, "--", "sh", "-c", "ps aux"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10)

# Run DNS operations on deployed pods
def dns_operations_worker():
    while True:
        for pod in DEPLOYED_PODS:
            logger.info(f"Running DNS operations on {pod}")
            subprocess.run(["kubectl", "exec", "-n", NAMESPACE, pod, "--", "sh", "-c", "nslookup google.com"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10)

# Deploy images in a round-robin manner across nodes
def deploy_vulnerable_images_balanced():
    try:
        nodes = get_all_nodes()
        node_count = len(nodes)
        if node_count == 0:
            logger.error("No available nodes for deployment.")
            return

        for index, image in enumerate(VULNERABLE_IMAGES):
            node = nodes[index % node_count]  # Round-robin distribution
            deployment_name = generate_deployment_name(image)
            logger.info(f"Deploying {image} as {deployment_name} in namespace {NAMESPACE} on node {node}")

            deployment = client.V1Deployment(
                metadata=client.V1ObjectMeta(name=deployment_name),
                spec=client.V1DeploymentSpec(
                    replicas=1,
                    selector=client.V1LabelSelector(match_labels={"app": deployment_name}),
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={"app": deployment_name}),
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

            apps_v1.create_namespaced_deployment(namespace=NAMESPACE, body=deployment)
            logger.info(f"Deployed {deployment_name} on node {node}")
            DEPLOYED_PODS.append(deployment_name)

    except Exception as e:
        logger.error(f"Error deploying images: {e}")

# Worker to deploy all images in a balanced way
def deployment_worker():
    delete_last_two_namespaces()  # Delete the last two namespaces before deployment
    create_namespace()
    deploy_vulnerable_images_balanced()
    
    # Start workers in parallel
    for _ in range(FILE_WORKERS):
        threading.Thread(target=file_operations_worker, daemon=True).start()
    for _ in range(PROCESS_WORKERS):
        threading.Thread(target=process_operations_worker, daemon=True).start()
    for _ in range(DNS_WORKERS):
        threading.Thread(target=dns_operations_worker, daemon=True).start()

# Start workers
def main():
    deployment_thread = threading.Thread(target=deployment_worker)
    deployment_thread.start()
    deployment_thread.join()
    logger.info("All deployments completed and operations executed. Script exiting.")

if __name__ == "__main__":
    main()
