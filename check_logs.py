import os
import subprocess

# Use the same output directory as other scripts
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/workspace/logs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ERROR_KEYWORDS = "error|fail|panic"

def get_filtered_logs(pod_name, check_previous=False):
    """Fetch logs of a specific pod and filter errors using grep."""
    cmd = f"kubectl logs {pod_name} -n kubescape | grep -iE '{ERROR_KEYWORDS}' || true"
    
    if check_previous:
        cmd = f"kubectl logs {pod_name} -n kubescape --previous | grep -iE '{ERROR_KEYWORDS}' || true"

    try:
        logs = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True)
        return logs.strip()
    except subprocess.CalledProcessError:
        return ""

def main():
    print("Fetching pods in 'kubescape' namespace...")

    pod_list_cmd = "kubectl get pods -n kubescape -o jsonpath='{.items[*].metadata.name}'"
    pod_list = subprocess.getoutput(pod_list_cmd).split()

    for pod in pod_list:
        print(f"Checking logs for pod: {pod}")
        
        # Check both current and previous logs
        logs_current = get_filtered_logs(pod)
        logs_previous = get_filtered_logs(pod, check_previous=True)

        combined_logs = "\n".join(filter(None, [logs_current, logs_previous]))  # Merge if both exist

        if combined_logs:  # Only create a file if errors are found
            pod_log_file = os.path.join(OUTPUT_DIR, f"{pod}_errors.log")
            with open(pod_log_file, "w") as log_file:
                log_file.write(combined_logs + "\n")
            print(f"⚠️ Errors detected in {pod}! Log saved to {pod_log_file}")
        else:
            print(f"No errors found in {pod}.")

if __name__ == "__main__":
    main()
