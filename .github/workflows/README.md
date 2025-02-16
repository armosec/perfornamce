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
| ACCOUNT_ID | Your account ID | string | N/A | ✅ |
| ACCESS_KEY | Your access key | string | N/A | ✅ |
| NODE_AGENT_VERSION | Node agent version | string | N/A | ❌ |
| ENABLE_KDR | Enable KDR | boolean | false | ❌ |
| PRIVATE_NODE_AGENT | Private node agent version | string | N/A | ❌ |
| HELM_GIT_BRANCH | Helm chart branch (e.g., main) | string | N/A | ❌ |

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

### Set Up Metrics Collection:

Fetches Helm chart versions deployed in the cluster.
Captures image versions of running containers.
Stores collected data in /workspace/Logs/performance-inCluster/ with a timestamp.

Execute the collect metrics job:

`get_data_from_prometheus.py` - Fetches metrics CPU and memory.

`get_pprof.py` - Collects profiling data of the node agent.

`check_logs.py` - Verifies logs for anomalies (looking for error / fail / panic).

#### Push Results to Logs Repository: Commits and pushes logs to GitHub for later analysis to the  [performance-inCluste](https://github.com/armosec/Logs/tree/main/performance-inCluster) repo

**Send Slack Notification**: Notifies the Slack channel [#performance-tests](https://app.slack.com/client/T020T1V84TT/C06AJ92GHLM) with details of the performance test run, including Helm chart versions and collected metrics.









