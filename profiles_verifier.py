from dataclasses import dataclass
import subprocess
import json
import os
import sys
import logging
import time
from typing import Dict, List, Optional, Any

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
    Profile: Optional[dict] = None
    NetworkNeighborhood: Optional[dict] = None

@dataclass
class VerificationRule:
    description: str
    execs: List[Dict[str, Any]]
    opens: List[Dict[str, Any]]
    network_connections: List[Dict[str, Any]]

class VerificationConfig:
    """
    Handles loading and managing verification rules from JSON configuration.
    """
    def __init__(self, config_file: str = "verification_rules.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self.verification_rules = self._parse_verification_rules()
        self.global_settings = self.config.get("global_settings", {})

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded verification configuration from {self.config_file}")
                return config
        except FileNotFoundError:
            logger.warning(f"Configuration file {self.config_file} not found. Using empty configuration.")
            return {"workload_verifications": {}, "global_settings": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing configuration file {self.config_file}: {e}")
            return {"workload_verifications": {}, "global_settings": {}}

    def _parse_verification_rules(self) -> Dict[str, VerificationRule]:
        """Parse verification rules from configuration."""
        rules = {}
        workload_verifications = self.config.get("workload_verifications", {})
        
        for workload_name, rule_data in workload_verifications.items():
            rules[workload_name] = VerificationRule(
                description=rule_data.get("description", ""),
                execs=rule_data.get("execs", []),
                opens=rule_data.get("opens", []),
                network_connections=rule_data.get("network_connections", [])
            )
        
        logger.info(f"Loaded {len(rules)} verification rules")
        return rules

    def get_verification_rule(self, workload_name: str) -> Optional[VerificationRule]:
        """Get verification rule for a specific workload."""
        return self.verification_rules.get(workload_name)

    def has_verification_rule(self, workload_name: str) -> bool:
        """Check if a verification rule exists for a workload."""
        return workload_name in self.verification_rules

class ProfilesVerifier:
    """
    This class is used to verify that all the application profiles and network neighborhoods are exist and valid.
    """
    def __init__(self, excluded_namespaces: List[str], timeout: int = 30, config_file: str = "verification_rules.json"):
        self._excluded_namespaces = excluded_namespaces
        self._timeout = timeout
        self._config = VerificationConfig(config_file)

    def _run_kubectl_command(self, cmd_args: List[str], retries: int = 3) -> dict:
        """
        Run kubectl command with retry logic and proper error handling.
        """
        for attempt in range(retries):
            try:
                logger.debug(f"Running kubectl command (attempt {attempt + 1}): {' '.join(cmd_args)}")
                
                # Add timeout and ensure we're using the right context
                result = subprocess.run(
                    cmd_args,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=self._timeout,
                    env={**os.environ, 'KUBECONFIG': os.environ.get('KUBECONFIG', '')}
                )
                
                if not result.stdout.strip():
                    logger.warning(f"Empty output from kubectl command: {' '.join(cmd_args)}")
                    if attempt < retries - 1:
                        time.sleep(1)  # Brief pause before retry
                        continue
                    return {}
                
                data = json.loads(result.stdout)
                return data
                
            except subprocess.TimeoutExpired:
                logger.error(f"Timeout running kubectl command (attempt {attempt + 1}): {' '.join(cmd_args)}")
                if attempt < retries - 1:
                    time.sleep(2)  # Longer pause for timeout
                    continue
                return {}
            except subprocess.CalledProcessError as e:
                logger.error(f"Error running kubectl command (attempt {attempt + 1}): {' '.join(cmd_args)}")
                logger.error(f"Return code: {e.returncode}")
                logger.error(f"stdout: {e.stdout}")
                logger.error(f"stderr: {e.stderr}")
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return {}
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error (attempt {attempt + 1}): {e}")
                logger.error(f"stdout: {result.stdout[:200]}...")  # First 200 chars
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return {}
        
        return {}

    def _get_all_workloads(self) -> List[Workload]:
        """
        Fetch all workloads (Deployments, StatefulSets, DaemonSets, Jobs) from all namespaces using kubectl,
        excluding those in self.excluded_namespaces. Only returns workloads that have at least one pod running.
        Returns a list of Workload objects.
        """
        workloads = []
        kinds = ["Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"]
        
        for kind in kinds:
            logger.info(f"Fetching {kind}s...")
            data = self._run_kubectl_command([
                "kubectl", "get", kind.lower() + "s", "--all-namespaces", "-o", "json"
            ])
            
            if not data:
                logger.warning(f"No data returned for {kind}s, skipping")
                continue
                
            for item in data.get("items", []):
                ns = item["metadata"]["namespace"]
                if ns in self._excluded_namespaces:
                    continue
                name = item["metadata"]["name"]
                
                # Check if the workload has at least one pod running
                if self._has_running_pods(kind, name, ns):
                    logger.info(f"Found workload {name} in namespace {ns} of kind {kind} with running pods")
                    workloads.append(Workload(Kind=kind, Name=name, Namespace=ns))
                else:
                    logger.info(f"Skipping workload {name} in namespace {ns} of kind {kind} - no running pods")
        
        logger.info(f"Total workloads with running pods found: {len(workloads)}")
        return workloads
    
    def _has_running_pods(self, kind: str, name: str, namespace: str) -> bool:
        """
        Check if a workload has at least one pod running.
        
        Args:
            kind: The kind of workload (Deployment, StatefulSet, DaemonSet, Job, CronJob)
            name: The name of the workload
            namespace: The namespace of the workload
            
        Returns:
            True if the workload has at least one pod running, False otherwise
        """
        try:
            # Get the workload to extract its selector
            workload_data = self._run_kubectl_command([
                "kubectl", "get", kind.lower(), name, "-n", namespace, "-o", "json"
            ])
            
            if not workload_data:
                logger.warning(f"Could not get workload {kind} {name} in namespace {namespace}")
                return False
            
            # Get pods using the workload's selector
            label_selector = self._get_label_selector_from_workload(workload_data, kind)
            if not label_selector:
                logger.warning(f"Could not determine label selector for {kind} {name} in namespace {namespace}")
                return False
            
            data = self._run_kubectl_command([
                "kubectl", "get", "pods", "-n", namespace, 
                "-l", label_selector, "-o", "json"
            ])
            
            if not data or not data.get("items"):
                return False
            
            # Check if any pod is running
            for pod in data.get("items", []):
                pod_status = pod.get("status", {})
                phase = pod_status.get("phase", "")
                
                # Consider pods as "running" if they are in Running phase with ready containers
                if phase == "Running":
                    container_statuses = pod_status.get("containerStatuses", [])
                    if any(container.get("ready", False) for container in container_statuses):
                        return True
                # For Pending pods, check if they're not in a failed state
                elif phase == "Pending":
                    # Check if pod is not in a failed condition
                    conditions = pod_status.get("conditions", [])
                    failed_conditions = [c for c in conditions if c.get("type") == "PodScheduled" and c.get("status") == "False"]
                    if not failed_conditions:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking running pods for {kind} {name} in namespace {namespace}: {e}")
            return False
    
    def _get_label_selector_from_workload(self, workload_data: dict, kind: str) -> Optional[str]:
        """
        Extract label selector from workload metadata.
        
        Args:
            workload_data: The workload JSON data
            kind: The kind of workload
            
        Returns:
            Label selector string or None if not found
        """
        try:
            spec = workload_data.get("spec", {})
            
            if kind in ["Deployment", "StatefulSet", "DaemonSet"]:
                # Get selector from spec.selector
                selector = spec.get("selector", {})
                match_labels = selector.get("matchLabels", {})
                
                if match_labels:
                    # Convert matchLabels to label selector string
                    label_pairs = [f"{k}={v}" for k, v in match_labels.items()]
                    return ",".join(label_pairs)
                    
            elif kind == "Job":
                # Jobs use job-name label
                return f"job-name={workload_data.get('metadata', {}).get('name', '')}"
                
            elif kind == "CronJob":
                # For CronJob, we need to check the Job it created
                # This is more complex as we need to find the actual Job
                return f"job-name={workload_data.get('metadata', {}).get('name', '')}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting label selector from workload: {e}")
            return None
    
    def verify_profiles(self):
        """
        Verify the profiles and network neighborhoods for all workloads.
        """
        workloads = self._get_all_workloads()
        logger.info(f"Starting verification for {len(workloads)} workloads")
        
        verification_results = {
            "total_workloads": len(workloads),
            "verified": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }
        
        for i, workload in enumerate(workloads, 1):
            logger.info(f"Verifying workload {i}/{len(workloads)}: {workload.Name} in namespace {workload.Namespace} of kind {workload.Kind}")
            
            try:
                result = self._verify_single_workload(workload)
                if result:
                    verification_results["verified"] += 1
                else:
                    verification_results["failed"] += 1
            except Exception as e:
                logger.error(f"Error verifying workload {workload.Name}: {e}")
                verification_results["errors"].append({
                    "workload": workload.Name,
                    "namespace": workload.Namespace,
                    "error": str(e)
                })
                verification_results["failed"] += 1
        
        self._log_verification_summary(verification_results)

    def _verify_single_workload(self, workload: Workload) -> bool:
        """Verify a single workload's profile and network neighborhood."""
        # Get profile
        profile = self._get_profile(workload)
        if profile is None:
            logger.error(f"Profile not found for workload {workload.Name} in namespace {workload.Namespace}")
            return False
        
        full_profile = self._get_full_profile(profile.get("metadata", {}).get("name"), profile.get("metadata", {}).get("namespace"))
        if full_profile is None:
            logger.error(f"Full profile not found for workload {workload.Name} in namespace {workload.Namespace}")
            return False
        workload.Profile = full_profile
        
        # Get network neighborhood
        network_neighborhood = self._get_network_neighborhood(workload)
        if network_neighborhood is None:
            logger.error(f"Network neighborhood not found for workload {workload.Name} in namespace {workload.Namespace}")
            return False
        
        full_network_neighborhood = self._get_full_network_neighborhood(
            network_neighborhood.get("metadata", {}).get("name"), 
            network_neighborhood.get("metadata", {}).get("namespace")
        )
        if full_network_neighborhood is None:
            logger.error(f"Full network neighborhood not found for workload {workload.Name} in namespace {workload.Namespace}")
            return False
        workload.NetworkNeighborhood = full_network_neighborhood
        
        # Verify basic status
        if not self._verify_profile_and_network_neighborhood(profile, network_neighborhood):
            logger.error(f"Profile or network neighborhood is not valid for workload {workload.Name} in namespace {workload.Namespace}")
            return False
        
        # Verify against configuration rules
        if not self._verify_against_configuration_rules(workload):
            logger.error(f"Workload {workload.Name} in namespace {workload.Namespace} does not match the configuration rules")
            return False
        
        logger.info(f"Profile and network neighborhood are valid for workload {workload.Name} in namespace {workload.Namespace}")
        return True

    def _get_profile(self, workload: Workload) -> Optional[dict]:
        """
        Get the profile for a workload by listing all and filtering by labels.
        """
        data = self._run_kubectl_command([
            "kubectl", "get", "applicationprofiles", "-n", workload.Namespace, "-o", "json"
        ])
        
        if not data:
            return None
            
        for item in data.get("items", []):
            labels = item.get("metadata", {}).get("labels", {})
            if (
                labels.get("kubescape.io/workload-kind") == workload.Kind and
                labels.get("kubescape.io/workload-name") == workload.Name and
                labels.get("kubescape.io/workload-namespace") == workload.Namespace
            ):
                return item
        return None
    
    def _get_network_neighborhood(self, workload: Workload) -> Optional[dict]:
        """
        Get the network neighborhood for a workload by listing all and filtering by labels.
        """
        data = self._run_kubectl_command([
            "kubectl", "get", "networkneighborhoods", "-n", workload.Namespace, "-o", "json"
        ])
        
        if not data:
            return None
            
        for item in data.get("items", []):
            labels = item.get("metadata", {}).get("labels", {})
            if (
                labels.get("kubescape.io/workload-kind") == workload.Kind and
                labels.get("kubescape.io/workload-name") == workload.Name and
                labels.get("kubescape.io/workload-namespace") == workload.Namespace
            ):
                return item
        return None
    
    def _get_full_network_neighborhood(self, network_neighborhood_name: str, namespace: str) -> Optional[dict]:
        """
        Get the full network neighborhood for a workload by listing all and filtering by labels.
        """
        data = self._run_kubectl_command([
            "kubectl", "get", "networkneighborhood", "-n", namespace, network_neighborhood_name, "-o", "json"
        ])
        
        # Handle both single object and list responses
        if "items" in data:
            return data.get("items", [])[0] if data.get("items", []) else None
        else:
            return data
    
    @staticmethod
    def _verify_profile_and_network_neighborhood(profile: dict, network_neighborhood: dict) -> bool:
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
    
    def _get_full_profile(self, profile_name: str, namespace: str) -> Optional[dict]:
        """
        Get the full profile for a workload by listing all and filtering by name.
        """
        logger.info(f"Getting full profile for {profile_name} in namespace {namespace}")
        data = self._run_kubectl_command([
            "kubectl", "get", "applicationprofile", "-n", namespace, profile_name, "-o", "json"
        ])
        
        if not data:
            return None
            
        # Handle both single object and list responses
        if "items" in data:
            return data.get("items", [])[0] if data.get("items", []) else None
        else:
            return data
    
    def _verify_execs(self, expected_execs: List[Dict[str, Any]], profile_execs: List[Dict[str, Any]]) -> bool:
        """
        Verify that the expected execs are present in the profile.
        """
        for expected_exec in expected_execs:
            expected_path = expected_exec.get("path")
            expected_args = expected_exec.get("args", [])
            
            # Find matching exec in profile by path
            matching_profile_exec = None
            for profile_exec in profile_execs:
                if profile_exec.get("path") == expected_path:
                    matching_profile_exec = profile_exec
                    break
            
            if matching_profile_exec is None:
                logger.error(f"[ERROR] Expected exec {expected_path} not found in profile")
                return False
            
            profile_args = matching_profile_exec.get("args", [])
            if expected_args != profile_args:
                logger.error(f"[ERROR] Expected args {expected_args} not found in profile for path {expected_path}")
                return False
        
        logger.info(f"[INFO] All expected execs are present in the profile")
        return True
    
    def _verify_opens(self, expected_opens: List[Dict[str, Any]], profile_opens: List[Dict[str, Any]]) -> bool:
        """
        Verify that the expected opens are present in the profile.
        """
        for expected_open in expected_opens:
            expected_path = expected_open.get("path")
            expected_flags = expected_open.get("flags", [])
            
            # Find matching open in profile by path
            matching_profile_open = None
            for profile_open in profile_opens:
                if profile_open.get("path") == expected_path:
                    matching_profile_open = profile_open
                    break
            
            if matching_profile_open is None:
                logger.error(f"[ERROR] Expected open {expected_path} not found in profile")
                return False
            
            profile_flags = matching_profile_open.get("flags", [])
            if expected_flags != profile_flags:
                logger.error(f"[ERROR] Expected flags {expected_flags} not found in profile for path {expected_path}")
                return False
        
        logger.info(f"[INFO] All expected opens are present in the profile")
        return True
    
    def _verify_network_connections(self, expected_network_connections: List[Dict[str, Any]], network_neighborhood: dict) -> bool:
        """
        Verify the network connections.
        # TODO: Improve this check
        """
        for expected_network_connection in expected_network_connections:
            expected_ingress = expected_network_connection.get("ingress", [])
            expected_egress = expected_network_connection.get("egress", [])
            
            container_spec = network_neighborhood.get("spec", {})
            container = container_spec.get("containers", [])[0]
            profile_ingress = container.get("ingress", [])
            profile_egress = container.get("egress", [])
            if len(expected_ingress) > 0:
                if expected_ingress[0].get("ports") != profile_ingress[0].get("ports"):
                    logger.error(f"[ERROR] Expected ingress ports {expected_ingress[0].get('ports')} not found in profile")
                    return False
            if len(expected_egress) > 0:
                if expected_egress[0].get("ports") != profile_egress[0].get("ports"):
                    logger.error(f"[ERROR] Expected egress ports {expected_egress[0].get('ports')} not found in profile")
                    return False
        return True
    
    def _verify_against_configuration_rules(self, workload: Workload) -> bool:
        """
        Verify the workload against configuration rules loaded from JSON.
        """
        workload_name = workload.Name.lower()
        rule = self._config.get_verification_rule(workload_name)
        
        if rule is None:
            if self._config.global_settings.get("log_missing_verifications", True):
                logger.info(f"No verification rule found for workload {workload_name}")
            return True
        
        logger.info(f"Verifying workload {workload_name} against configuration rules: {rule.description}")
        
        # Get profile data
        profile_spec = workload.Profile.get("spec", {})
        containers = profile_spec.get("containers", [])
        
        if not containers:
            logger.warning(f"No containers found in profile for workload {workload_name}")
            return False
        
        container = containers[0]  # Assume first container for now
        
        # Verify execs
        if rule.execs:
            profile_execs = container.get("execs", [])
            logger.info(f"Profile execs: {profile_execs}")
            logger.info(f"Rule execs: {rule.execs}")
            if not self._verify_execs(rule.execs, profile_execs):
                return False
        
        # Verify opens
        if rule.opens:
            profile_opens = container.get("opens", [])
            if not self._verify_opens(rule.opens, profile_opens):
                return False
        
        # Verify network connections
        if rule.network_connections:
            if not self._verify_network_connections(rule.network_connections, workload.NetworkNeighborhood):
                return False
        return True
    def _log_verification_summary(self, results: Dict[str, Any]):
        """Log a summary of verification results."""
        logger.info("=" * 50)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total workloads: {results['total_workloads']}")
        logger.info(f"Successfully verified: {results['verified']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info(f"Skipped: {results['skipped']}")
        
        if results['errors']:
            logger.info("Errors encountered:")
            for error in results['errors']:
                logger.error(f"  - {error['workload']} ({error['namespace']}): {error['error']}")
        
        success_rate = (results['verified'] / results['total_workloads'] * 100) if results['total_workloads'] > 0 else 0
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info("=" * 50)

if __name__ == "__main__":
    verifier = ProfilesVerifier(
        excluded_namespaces=["kubescape", "kube-system", "kube-public", "kube-node-lease", "kubeconfig", "gmp-system", "gmp-public"]
    )
    verifier.verify_profiles()
    