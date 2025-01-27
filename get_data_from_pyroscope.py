import glob, os, requests, subprocess, json
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# PYROSCOPE_SERVER = ‘http://localhost:4040/pyroscope’
PYROSCOPE_SERVER = 'http://pyroscope-query-frontend.monitoring.svc.cluster.local.:4040'
OUTPUT_DIR = 'output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

EXACT_DURATION = int(os.getenv('EXACT_DURATION'))

def get_node_agent_pods():
    try:
        cmd = "kubectl get pods -n kubescape --no-headers -o custom-columns=':metadata.name' | grep node-agent"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        pods = [pod.strip() for pod in result.stdout.split('\n') if pod.strip()]
        logger.info(f"Found {len(pods)} node-agent pods: {pods}")
        return pods
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting node-agent pods: {e}")
        return []

def get_pod_profile(pod_name):
    url = f'{PYROSCOPE_SERVER}/debug/pprof/heap'
    params = {'debug': '1'}
    
    try:
        logger.info(f"Getting heap profile for {pod_name}")
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        flamebearer_data = {
            'names': [],
            'levels': [],
            'numTicks': 0
        }
        
        total_bytes = 0
        stack_data = []
        
        for line in response.text.splitlines():
            if line.strip() and not line.startswith('#') and not line.startswith('heap profile:'):
                parts = line.split()
                if len(parts) >= 4:
                    bytes_used = int(parts[0])
                    total_bytes += bytes_used
                    func_name = ' '.join(parts[3:])
                    if func_name not in flamebearer_data['names']:
                        flamebearer_data['names'].append(func_name)
                    stack_data.append({
                        'bytes': bytes_used,
                        'name_idx': flamebearer_data['names'].index(func_name)
                    })
        
        if stack_data:
            level = []
            pos = 0
            for stack in stack_data:
                level.extend([pos, stack['bytes'], stack['bytes'], stack['name_idx']])
                pos += stack['bytes']
            flamebearer_data['levels'].append(level)
            flamebearer_data['numTicks'] = total_bytes
        
        output_file = os.path.join(OUTPUT_DIR, f'pyroscope_profile_data_{pod_name}.json')
        with open(output_file, 'w') as f:
            json.dump({'flamebearer': flamebearer_data}, f, indent=4)
            
        return True
    except Exception as e:
        logger.error(f'Error getting profile for {pod_name}: {e}')
        return False

def main():
    logger.info(f"Starting profile collection")
    pods = get_node_agent_pods()
    
    if not pods:
        logger.error("No node-agent pods found")
        return
    
    successful = 0
    for pod in pods:
        if get_pod_profile(pod):
            successful += 1
    
    logger.info(f"Successfully collected {successful}/{len(pods)} profiles")

if __name__ == "__main__":
    main()