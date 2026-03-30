# eBPF Dedup Benchmark — How to Run

The `dedup-bench.sh` script automates A/B performance testing of the node-agent's eBPF event deduplication feature. It creates a Kind cluster, installs Prometheus and Kubescape, runs a load simulator, and collects before/after metrics.

## Prerequisites

- **kind** — Kubernetes in Docker
- **helm** — Kubernetes package manager
- **kubectl** — Kubernetes CLI
- **docker** — Container runtime
- **python3** — For metrics collection and comparison (venv created automatically)
- **Hardware**: 8+ CPUs, 16+ GB RAM recommended for stable results

## Running Against the Open-Source Node-Agent

Use the `kubescape` helm chart (default mode):

```bash
cd perfornamce

# Build the test image first (from the node-agent directory)
cd ../node-agent
make binary
make docker-build IMAGE=quay.io/kubescape/node-agent TAG=dedup-test

# Run the benchmark
cd ../perfornamce
./dedup-bench.sh quay.io/kubescape/node-agent:v0.3.71 quay.io/kubescape/node-agent:dedup-test
```

### Arguments

```
./dedup-bench.sh <before-image> <after-image>
```

- `<before-image>` — Baseline node-agent image (e.g., a released version)
- `<after-image>` — Test node-agent image with the changes to benchmark

## Running Against the Private Node-Agent (ARMO Chart)

Use the `armo` helm mode with credentials:

```bash
cd perfornamce

# Build the test image first (from the private-node-agent directory)
cd ../private-node-agent
make node
make docker-build IMAGE=quay.io/armosec/node-agent TAG=dedup-test

# Run the benchmark
cd ../perfornamce
HELM_MODE=armo \
ARMO_ACCOUNT=<your-account-id> \
ARMO_ACCESS_KEY=<your-access-key> \
ARMO_IMAGE_PULL_SECRET=<your-pull-secret> \
ARMO_SERVER=api-dev.armosec.io \
./dedup-bench.sh quay.io/armosec/node-agent:v0.0.240 quay.io/armosec/node-agent:dedup-test
```

### Required Environment Variables (ARMO mode)

| Variable | Description |
|----------|-------------|
| `HELM_MODE` | Set to `armo` to use the private armosec chart |
| `ARMO_ACCOUNT` | ARMO account ID |
| `ARMO_ACCESS_KEY` | ARMO access key |
| `ARMO_IMAGE_PULL_SECRET` | Docker registry pull secret for quay.io/armosec |
| `ARMO_SERVER` | ARMO API server (e.g., `api-dev.armosec.io`) |

## What the Benchmark Does

1. **Creates Kind cluster** — 2 nodes (control-plane + worker)
2. **Installs Prometheus** — kube-prometheus-stack with 10s scrape interval
3. **BEFORE run** — Installs Kubescape with the baseline image, deploys load simulator, runs for 10 min (after 2 min warmup), collects metrics
4. **AFTER run** — Swaps node-agent to the test image, runs same load, collects metrics
5. **Comparison** — Runs `compare-metrics.py` to produce a summary table
6. **Cleanup** — Deletes Kind cluster

Estimated runtime: ~35 minutes.

## Output

Results are saved to `perfornamce/dedup-bench-output/`:

```
dedup-bench-output/
├── before/
│   ├── cpu_metrics.csv          # CPU time series (all kubescape pods)
│   ├── memory_metrics.csv       # Memory time series
│   ├── dedup_total.json         # Dedup counter metrics (empty for baseline)
│   ├── events_total.json        # Event counter metrics
│   ├── rule_total.json          # Rule firing metrics
│   └── *_cpu_usage.png          # Per-pod CPU graphs
│   └── *_memory_usage.png       # Per-pod memory graphs
└── after/
    └── (same structure)
```

The comparison summary is printed to stdout at the end of the run.

## Tuning Parameters

Edit the variables at the top of `dedup-bench.sh`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOAD_DURATION` | 600 | Load phase duration in seconds |
| `WARMUP_SECONDS` | 120 | Warmup period before measurement |
| `METRICS_DURATION` | 10 | Prometheus query window in minutes |
| `PROM_LOCAL_PORT` | 9090 | Local port for Prometheus port-forward |

The load simulator config is embedded in the script (see `deploy_load_simulator`). Adjust rates in the configmap to simulate different workloads.

## Troubleshooting

- **Node-agent ImagePullBackOff**: For private images, ensure `ARMO_IMAGE_PULL_SECRET` is correct and the `HELM_MODE=armo` prefix is set
- **Timeout waiting for pods**: The script uses 10m helm timeout and 600s kubectl wait. If your network is slow, increase these in the script
- **Port 9090 in use**: Change `PROM_LOCAL_PORT` to an available port
- **Low CPU/memory warnings**: Run on a machine with 8+ CPUs and 16+ GB RAM for reproducible results
