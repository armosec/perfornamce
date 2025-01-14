import subprocess
import time
from datetime import datetime, timedelta
import argparse
import sys

def wait_duration(minutes):
    """Wait for the specified duration and log progress"""
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=minutes)
    
    print(f"\nStarting metrics collection wait period at: {start_time}")
    print(f"Will wait for {minutes} minutes until: {end_time}")
    
    try:
        while datetime.now() < end_time:
            time.sleep(30)  # Check every 30 seconds for shorter duration
            remaining = end_time - datetime.now()
            minutes_left = remaining.total_seconds() / 60
            
            # For short durations, log more frequently (every minute)
            if remaining.seconds % 60 < 5:  # Log within first 5 seconds of each minute
                print(f"Waiting... {minutes_left:.1f} minutes remaining")
                
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        raise
        
    print(f"\nWait period completed at: {datetime.now()}")
    print(f"Total wait time: {datetime.now() - start_time}")

def collect_metrics():
    """Run the metrics collection scripts"""
    print("\nCollecting Prometheus metrics...")
    subprocess.run(["python", "get_data_from_prometheus.py"], check=True)
    
    print("\nCollecting Pyroscope data...")
    subprocess.run(["python", "get_data_from_pyroscope.py"], check=True)
    
    print("\nParsing Pyroscope data...")
    subprocess.run(["python", "parse_pyroscope_data.py"], check=True)

def main():
    parser = argparse.ArgumentParser(description="Wait specified duration and collect metrics")
    parser.add_argument('--duration', type=int, required=True, help="Duration to wait in minutes")
    args = parser.parse_args()

    try:
        # Wait for the specified duration
        wait_duration(args.duration)

        # Collect metrics
        collect_metrics()

    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()