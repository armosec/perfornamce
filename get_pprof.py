import requests
import argparse
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

# Constants
# PYROSCOPE_URL = "http://localhost:4040"
PYROSCOPE_URL = 'http://pyroscope-query-frontend.monitoring.svc.cluster.local:4040'

class PyroscopeClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def get_profile(self, service_name: str, pod_name: str, from_time: datetime, until_time: datetime, query_type: str = "memory") -> Dict[str, Any]:
        """Fetch profile data in JSON format from Pyroscope API"""
        endpoint = f"{self.base_url}/pyroscope/render"
        query = f"{query_type}:inuse_objects:count:space:bytes{{service_name=\"{service_name}\",pod=\"{pod_name}\"}}"
        
        params = {
            'query': query,
            'from': int(from_time.timestamp() * 1000),
            'until': int(until_time.timestamp() * 1000),
            'format': 'json',
            'aggregation': 'sum'
        }

        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching profile data for pod {pod_name}: {e}")
            return {}

def get_node_agent_pods() -> List[str]:
    """Get all node-agent pod names in the kubescape namespace"""
    try:
        cmd = "kubectl get pods -n kubescape --no-headers -o custom-columns=':metadata.name' | grep node-agent"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        pods = [pod.strip() for pod in result.stdout.split('\n') if pod.strip()]
        print(f"Found {len(pods)} node-agent pods: {pods}")
        return pods
    except subprocess.CalledProcessError as e:
        print(f"Error getting node-agent pods: {e}")
        return []
    
def convert_to_speedscope(profile_data: Dict[str, Any], pod_name: str) -> Dict[str, Any]:
    """
    Convert Pyroscope JSON format to speedscope format
    """
    if not profile_data or 'flamebearer' not in profile_data:
        return {}

    flamebearer = profile_data['flamebearer']
    
    speedscope = {
        "version": "0.0.7",
        "shared": {
            "frames": [{"name": name} for name in flamebearer['names']]
        },
        "profiles": [{
            "type": "sampled",
            "name": f"Memory Profile - {pod_name}",
            "unit": "bytes",
            "startValue": 0,
            "endValue": flamebearer['numTicks'],
            "samples": [],
            "weights": []
        }]
    }

    current_sample = []
    for level in flamebearer['levels']:
        for i in range(0, len(level), 4):
            if i + 3 >= len(level):
                continue
            
            value = level[i + 1]
            name_idx = level[i + 3]
            
            if name_idx is not None:
                current_sample.append(name_idx)
                speedscope['profiles'][0]['samples'].append(list(current_sample))
                speedscope['profiles'][0]['weights'].append(value)

    return speedscope


def main():
    # Read EXACT_DURATION from environment (default to 30 minutes)
    duration_minutes = int(os.getenv('EXACT_DURATION', '30'))
    print(f"Using EXACT_DURATION={duration_minutes} minutes from environment")

    # Calculate time range
    until_time = datetime.now(timezone.utc)
    from_time = until_time - timedelta(minutes=duration_minutes)

    # Create output directory
    output_dir = Path("output/profiles")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all node-agent pods
    pods = get_node_agent_pods()
    if not pods:
        print("No node-agent pods found!")
        return

    # Initialize client
    client = PyroscopeClient(PYROSCOPE_URL)

    # Process each pod
    for pod_name in pods:
        print(f"\nProcessing pod: {pod_name}")

        # Get profile data
        profile_data = client.get_profile("node-agent", pod_name, from_time, until_time)
        
        if profile_data:
            # Convert to speedscope format
            speedscope_data = convert_to_speedscope(profile_data, pod_name)
            
            if speedscope_data:
                # Generate output filename using UTC timestamp
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
                output_file = output_dir / f"{pod_name}_{timestamp}.speedscope.json"
                
                # Write to file
                with open(output_file, 'w') as f:
                    json.dump(speedscope_data, f)
                print(f"Profile saved to {output_file}")
            else:
                print(f"Failed to convert profile data for {pod_name}")
        else:
            print(f"Failed to fetch profile data for {pod_name}")

if __name__ == "__main__":
    main()