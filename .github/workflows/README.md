# DigitalOcean Kubernetes Cluster Setup

This GitHub Actions workflow automates the creation of a Kubernetes cluster on DigitalOcean, configures `kubectl`, and runs a performance test.

## Workflow Trigger
The workflow is manually triggered using `workflow_dispatch` with user-defined inputs.

## Inputs
| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| CLUSTER_NAME | Name of the Kubernetes cluster | string | perfo-cluster | ✅ |
| NODE_SIZE | Size of the nodes | choice | s-8vcpu-16gb | ✅ |
| NODE_COUNT | Number of nodes | number | 4 | ✅ |
| DURATION_TIME | Duration before collecting metrics (minutes) | number | 10 | ✅ |
| KUBERNETES_VERSION | Kubernetes version to use | string | N/A | ❌ |
| STORAGE_VERSION | storage version | string | N/A | ❌ |
| NODE_AGENT_VERSION | Node agent version | string | N/A | ❌ |
| ENABLE_KDR | Enable KDR | boolean | false | ❌ |
| PRIVATE_NODE_AGENT | Private node agent version | string | N/A | ❌ |
| HELM_GIT_BRANCH | Helm chart branch (e.g., main) | string | N/A | ❌ |
| ADDITIONAL_HELM_COMMAND | Additional Helm command-line arguments to customize the Kubescape deployment (e.g., extra --set flags) | string | N/A | ❌ |

##
#### Tip:
You can use `ADDITIONAL_HELM_COMMAND` to inject extra flags into the Helm install/upgrade command (e.g., custom image repositories, new feature toggles, etc.).
```
 --set capabilities.httpDetection=enable, --set capabilities.runtimeDetection=enable
```


## Jobs & Steps
### 1. Setup Cluster
#### Steps:
1. **Checkout Repository**: Clones the repository.
2. **Install `kubectl`**: Installs and verifies `kubectl`.
3. **Install `doctl`**: Installs `doctl` to interact with DigitalOcean.
4. **Create Kubernetes Cluster**: Creates a DigitalOcean K8s cluster with specified node size and count.
5. **Configure `kubectl`**: Saves and configures cluster context.
6. **Connect to Cluster**: Fetches cluster details and configures `kubectl`.

### 2. Run Performance Test
#### Steps:
1. Runs a Python performance test script with dynamic parameters.
2. Supports optional parameters like storage version, node agent version, and KDR enablement.

### 3. Deploy Metrics Collection Job
#### Steps:
1. Deploys `collect-metrics-job.yaml` with a runtime-defined timestamp.
2. Specifies metric collection duration from user input.

    #### Set Up Metrics Collection:

    Fetches Helm chart versions deployed in the cluster.
    Captures image versions of running containers.
    Stores collected data in /workspace/Logs/performance-inCluster/ with a timestamp.

    Execute the collect metrics job:

    `get_data_from_prometheus.py` - Fetches metrics CPU and memory.

    `get_pprof.py` - Collects profiling data of the node agent.

    `check_logs.py` - Verifies logs for anomalies (looking for error / fail / panic).

    `profiles_verifier.py` - Verifies that all the application profiles and network neighborhods are exist and valid.
    
    `threshold_check.py` -  Verifies CPU and memory usage against thresholds (fetched from a Kubernetes ConfigMap) and generates a summary JSON report if any breaches are detected. It analyzes the collected metrics and flags pods that exceeded their thresholds for more than 5 seconds.


### 4. Deploy Load Generator Job

This section includes a Kubernetes Job that deploys a load generator to simulate real-world usage and stress test your cluster with vulnerable applications and periodic operations.

- **Python Script (`load-generator.py`)**:
  - Creates a new namespace dynamically.
  - Deploys multiple vulnerable images as DaemonSets across all nodes.
  - Spawns parallel threads to simulate:
    - File system operations
    - Process execution
    - DNS resolution
- **Job Definition**: A Kubernetes Job that starts the load generator using a Python-based container.

#### How It Works

1. **Startup Delay**: The script waits 60 minutes after the container starts to delay the initial load.
2. **Namespace Handling**:
   - Deletes up to one non-critical namespace per node.
   - Creates a new unique namespace (e.g., `new-load-1`, `new-load-2`, etc.).
3. **Deployment of Vulnerable Applications**:
   - Each vulnerable image is deployed as a DaemonSet.
   - Ensures each node runs at least one vulnerable pod.
4. **Simulated Operations** (in parallel threads):
   - **File Workers**: Create and delete files periodically inside pods.
   - **Process Workers**: Run `ps aux` to simulate process activity.
   - **DNS Workers**: Perform DNS lookups (e.g., `nslookup google.com`) inside pods.
5. **Repetition**: After each full run, it waits 60 minutes and repeats the load generation.

## Outputs
**1. Results to Logs Repository:** Commits and pushes logs to GitHub for later analysis to the  [performance-inCluste](https://github.com/armosec/Logs/tree/main/performance-inCluster) repo.

 **2. pprof profiles:** you can open via [speedscope](https://www.speedscope.app/)

**3. Slack Notification**: Notifies the Slack channel [#performance-tests](https://app.slack.com/client/T020T1V84TT/C06AJ92GHLM) with details of the performance test run, including Helm chart versions and collected metrics.

**4. Scan results:**  in ARMO account `HelmPerformance` (account ID: 5a02d4af-8026-414f-9baf-fde6b2051136)









