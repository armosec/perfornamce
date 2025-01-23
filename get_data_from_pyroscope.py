import os
import requests
from datetime import datetime, timezone
import json
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# PYROSCOPE_SERVER = 'http://localhost:4040/pyroscope'
PYROSCOPE_SERVER = 'http://pyroscope-distributor.monitoring.svc.cluster.local:4040/pyroscope'
OUTPUT_DIR = 'output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Get exact duration from environment variable
EXACT_DURATION = int(os.getenv('EXACT_DURATION'))
logger.info(f"Using exact duration of {EXACT_DURATION} minutes from test run")

def get_node_agent_pods():
    """Get list of all node-agent pods in the kubescape namespace"""
    try:
        cmd = "kubectl get pods -n kubescape -l app=node-agent --no-headers -o custom-columns=':metadata.name'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        
        pods = [pod.strip() for pod in result.stdout.split('\n') if pod.strip()]
        logger.info(f"Found {len(pods)} node-agent pods: {pods}")
        return pods
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting node-agent pods: {e}")
        return []

def get_pod_profile(pod_name):
    """Get profile data for a specific pod"""
    APPLICATION_NAME = f'memory:inuse_space:bytes:space:bytes{{service_name="node-agent", pod="{pod_name}"}}'
    
    url = f'{PYROSCOPE_SERVER}/render'
    params = {
        'query': APPLICATION_NAME,
        'from': f'now-{EXACT_DURATION}m',  # Use exact duration from the test run
        'until': 'now',
        'aggregation': 'sum',
        'format': 'json'
    }
    
    try:
        logger.info(f"Querying profile data for pod {pod_name} over past {EXACT_DURATION} minutes")
        response = requests.get(url, params=params)
        response.raise_for_status()
        profile_data = response.json()
        
        output_file = os.path.join(OUTPUT_DIR, f'pyroscope_profile_data_{pod_name}.json')
        with open(output_file, 'w') as f:
            json.dump(profile_data, f, indent=4)
        
        logger.info(f'Profile data saved to {output_file}')
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f'Error querying Pyroscope for pod {pod_name}: {e}')
        return False
    except json.JSONDecodeError as e:
        logger.error(f'Error parsing JSON response for pod {pod_name}: {e}')
        return False
    except Exception as e:
        logger.error(f'Unexpected error processing pod {pod_name}: {e}')
        return False

def main():
    logger.info(f"Starting profile collection for the past {EXACT_DURATION} minutes")
    
    pods = get_node_agent_pods()
    if not pods:
        logger.error("No node-agent pods found")
        return
    
    successful_pods = 0
    for pod in pods:
        if get_pod_profile(pod):
            successful_pods += 1
    
    logger.info(f"Process complete. Successfully collected profiles for {successful_pods}/{len(pods)} pods")
    logger.info(f"Time window: past {EXACT_DURATION} minutes")

if __name__ == "__main__":
    main()