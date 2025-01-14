import requests
from datetime import datetime, timezone
import json

# Configuration
PYROSCOPE_SERVER = 'http://localhost:4040/pyroscope'
APPLICATION_NAME = 'memory:inuse_space:bytes:space:bytes{service_name="node-agent", pod="node-agent-gsvpn"}'
OUTPUT_FILE = 'pyroscope_profile_data.json'

# Construct the query URL
url = f'{PYROSCOPE_SERVER}/render'
params = {
    'query': APPLICATION_NAME,
    'from': 'now-5m',
    'until': 'now',
    'aggregation': 'sum',
    'format': 'json'
}

# Send the GET request to the Pyroscope server
try:
    response = requests.get(url, params=params)
    response.raise_for_status()  # Raise an error for bad status codes
    profile_data = response.json()
    
    # Save the retrieved data to a JSON file
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(profile_data, f, indent=4)
    
    print(f'Profile data saved to {OUTPUT_FILE}')
except requests.exceptions.RequestException as e:
    print(f'Error querying Pyroscope: {e}')