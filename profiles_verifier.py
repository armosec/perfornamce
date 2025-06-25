from dataclasses import dataclass
import subprocess
import json
import os
import sys
import logging

# Set up logging to file in logs directory (same as check_logs.py)
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/workspace/logs")
LOG_FILE = os.path.join(OUTPUT_DIR, "profiles_verifier.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, mode='w'), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

@dataclass
class Workload:
    Kind: str
    Name: str
    Namespace: str

class ProfilesVerifier:
    """
    This class is used to verify that all the application profiles and network neighborhods are exist and valid.
    """
    def __init__(self, excluded_namespaces: list[str]):
        self._excluded_namespaces = excluded_namespaces

    def _get_all_workloads(self) -> list[Workload]:
        """
        Fetch all workloads (Deployments, StatefulSets, DaemonSets, Jobs) from all namespaces using kubectl,
        excluding those in self.excluded_namespaces. Returns a list of Workload objects.
        """
        workloads = []
        kinds = ["Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"]
        for kind in kinds:
            try:
                result = subprocess.run(
                    [
                        "kubectl", "get", kind.lower() + "s", "--all-namespaces", "-o", "json"
                    ],
                    capture_output=True, text=True, check=True
                )
                data = json.loads(result.stdout)
                for item in data.get("items", []):
                    ns = item["metadata"]["namespace"]
                    if ns in self._excluded_namespaces:
                        continue
                    name = item["metadata"]["name"]
                    logger.info(f"Found workload {name} in namespace {ns} of kind {kind}")
                    workloads.append(Workload(Kind=kind, Name=name, Namespace=ns))
            except subprocess.CalledProcessError as e:
                logger.error(f"Error getting {kind}s: {e}")
                continue
        return workloads
    
    def verify_profiles(self):
        """
        Verify the profiles and network neighborhods for all workloads.
        """
        for workload in self._get_all_workloads():
            logger.info(f"Verifying workload {workload.Name} in namespace {workload.Namespace} of kind {workload.Kind}")
            profile = self._get_profile(workload)
            if profile is None:
                logger.error(f"Profile not found for workload {workload.Name} in namespace {workload.Namespace}")
                continue
            network_neighborhood = self._get_network_neighborhood(workload)
            if network_neighborhood is None:
                logger.error(f"Network neighborhood not found for workload {workload.Name} in namespace {workload.Namespace}")
                continue
            if not self._verify_profile_and_network_neighborhood(profile, network_neighborhood):
                logger.error(f"Profile or network neighborhood is not valid for workload {workload.Name} in namespace {workload.Namespace}")
                continue
            logger.info(f"Profile and network neighborhood are valid for workload {workload.Name} in namespace {workload.Namespace}")

    @staticmethod
    def _get_profile(workload: Workload) -> dict:
        """
        Get the profile for a workload by listing all and filtering by labels.
        """
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "applicationprofile", "-n", workload.Namespace, "-o", "json"
                ],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            for item in data.get("items", []):
                labels = item.get("metadata", {}).get("labels", {})
                if (
                    labels.get("kubescape.io/workload-kind") == workload.Kind and
                    labels.get("kubescape.io/workload-name") == workload.Name and
                    labels.get("kubescape.io/workload-namespace") == workload.Namespace
                ):
                    return item
            return None
        except subprocess.CalledProcessError as e:
            return None
    
    @staticmethod
    def _get_network_neighborhood(workload: Workload) -> dict:
        """
        Get the network neighborhood for a workload by listing all and filtering by labels.
        """
        try:
            result = subprocess.run(
                [
                    "kubectl", "get", "networkneighborhood", "-n", workload.Namespace, "-o", "json"
                ],
                capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)
            for item in data.get("items", []):
                labels = item.get("metadata", {}).get("labels", {})
                if (
                    labels.get("kubescape.io/workload-kind") == workload.Kind and
                    labels.get("kubescape.io/workload-name") == workload.Name and
                    labels.get("kubescape.io/workload-namespace") == workload.Namespace
                ):
                    return item
            return None
        except subprocess.CalledProcessError as e:
            return None
    
    @staticmethod
    def _verify_profile_and_network_neighborhood(profile: dict, network_neighborhood: dict):
        """
        Verify the profile and network neighborhood.
        To verify the profile we check if the annotation "kubescape.io/status" is "completed".
        To verify the network neighborhood we check if the annotation "kubescape.io/status" is "completed".
        """
        if profile.get("metadata", {}).get("annotations", {}).get("kubescape.io/status") != "completed":
            logger.error(f"[ERROR] Profile {profile.get('metadata', {}).get('name')} in namespace {profile.get('metadata', {}).get('namespace')} is not completed")
            return False
        if network_neighborhood.get("metadata", {}).get("annotations", {}).get("kubescape.io/status") != "completed":
            logger.error(f"[ERROR] Network neighborhood {network_neighborhood.get('metadata', {}).get('name')} in namespace {network_neighborhood.get('metadata', {}).get('namespace')} is not completed")
            return False
        return True

if __name__ == "__main__":
    verifier = ProfilesVerifier(excluded_namespaces=["kubescape", "kube-system", "kube-public", "kube-node-lease", "kubeconfig", "gmp-system", "gmp-public"])
    verifier.verify_profiles()