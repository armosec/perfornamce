import os
import pandas as pd
import logging
from typing import Optional, Dict, List
import json
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_thresholds():
    """Fetch the latest thresholds from the Kubernetes ConfigMap and apply a 15% increase."""
    try:
        # Fetch ConfigMap data from Kubernetes
        result = subprocess.run(
            ["kubectl", "get", "configmap", "pod-thresholds", "-n", "default", "-o", "jsonpath={.data.pod_thresholds\\.json}"],
            capture_output=True, text=True, check=True
        )

        raw_json = result.stdout.strip()

        if not raw_json:
            logger.error("ConfigMap `pod-thresholds` is empty or missing.")
            return None

        # Log the raw JSON for debugging
        logger.info(f"Raw ConfigMap JSON: {raw_json}")

        pod_thresholds = json.loads(raw_json)

        if not isinstance(pod_thresholds, dict):
            logger.error(f"Unexpected JSON format: {pod_thresholds}")
            return None

        # Apply 15% increase to each value
        updated_thresholds = {
            pod: {
                "Memory": round(metrics["Memory"] * 1.15, 2),
                "CPU": round(metrics["CPU"] * 1.15, 2)
            }
            for pod, metrics in pod_thresholds.items()
        }

        logger.info(f"Updated pod thresholds: {updated_thresholds}")
        return updated_thresholds

    except Exception as e:
        logger.error(f"Failed to load thresholds from ConfigMap: {e}")
        return None


class ThresholdChecker:
    def __init__(
        self,
        output_dir: str = "output",
        duration_threshold: int = 30,  # in seconds
        pod_thresholds: Optional[Dict[str, Dict[str, float]]] = None
    ):
        self.output_dir = output_dir
        self.duration_threshold = duration_threshold
        self.pod_thresholds = pod_thresholds or {}
        
        self.violations = {
            "Memory": [],
            "CPU": []
        }

    def calculate_breach_percentage(self, value: float, threshold: float) -> float:
        """Calculate how much the value exceeded the threshold by percentage."""
        return ((value - threshold) / threshold) * 100

    def get_threshold(self, pod: str, metric_type: str) -> Optional[float]:
        """Get the threshold for a specific pod and metric type."""
        if pod in self.pod_thresholds and metric_type in self.pod_thresholds[pod]:
            return self.pod_thresholds[pod][metric_type]
        return None

    def check_thresholds(self, file_path: str, metric_type: str) -> None:
        """Check if any values exceed the threshold for a sustained period."""
        if not os.path.exists(file_path):
            logger.info(f"File {file_path} not found. Skipping {metric_type} analysis.")
            return
        
        try:
            df = pd.read_csv(file_path)
            if df.empty:
                logger.info(f"{metric_type} data file is empty.")
                return
            
            df["Time"] = pd.to_datetime(df["Time"])
            
            # Analyze each pod separately
            for pod in df["Pod"].unique():
                pod_data = df[df["Pod"] == pod].copy()
                pod_data = pod_data.sort_values("Time")
                
                # Get the threshold for the current pod
                threshold = self.get_threshold(pod, metric_type)
                if threshold is None:
                    logger.warning(f"No threshold defined for pod {pod} and metric {metric_type}. Skipping.")
                    continue
                
                # Find periods where threshold is exceeded
                pod_data["violation"] = pod_data["Value"] > threshold
                pod_data["violation_group"] = (
                    pod_data["violation"] != pod_data["violation"].shift()
                ).cumsum()
                
                # Analyze each violation period
                for _, group in pod_data[pod_data["violation"]].groupby("violation_group"):
                    duration_seconds = (
                        group["Time"].max() - group["Time"].min()
                    ).total_seconds()
                    
                    if duration_seconds >= self.duration_threshold:
                        max_value = round(group["Value"].max(), 2)
                        avg_value = round(group["Value"].mean(), 2)
                        breach_pct = self.calculate_breach_percentage(max_value, threshold)
                        
                        violation = {
                            "pod": pod,
                            "start_time": group["Time"].min().isoformat(),
                            "end_time": group["Time"].max().isoformat(),
                            "duration_seconds": round(duration_seconds, 2),
                            "max_value": max_value,
                            "avg_value": avg_value,
                            "threshold": threshold,
                            "breach_percentage": round(breach_pct, 2)
                        }
                        
                        self.violations[metric_type].append(violation)
                        
                        # Log the violation with detailed information
                        unit = "MiB" if metric_type == "Memory" else "cores"
                        logger.warning(
                            f"\n{metric_type} threshold breach detected:"
                            f"\nPod: {pod}"
                            f"\n- Breach Period: {violation['start_time']} to {violation['end_time']}"
                            f"\n- Duration: {duration_seconds:.2f} seconds"
                            f"\n- Peak Usage: {max_value} {unit} ({breach_pct:.1f}% over threshold)"
                            f"\n- Average Usage: {avg_value} {unit}"
                            f"\n- Threshold: {threshold} {unit}"
                        )
                        
        except Exception as e:
            logger.error(f"Error analyzing {metric_type} data: {str(e)}")

    def generate_report(self) -> Dict:
        """Generate a summary report of all violations."""
        # Group violations by pod
        pod_summary = {}
        for metric_type, violations in self.violations.items():
            for violation in violations:
                pod = violation["pod"]
                if pod not in pod_summary:
                    pod_summary[pod] = {"Memory": 0, "CPU": 0}
                pod_summary[pod][metric_type] += 1

        return {
            "summary": {
                "total_memory_violations": len(self.violations["Memory"]),
                "total_cpu_violations": len(self.violations["CPU"]),
                "violations_by_pod": pod_summary,
                "thresholds": {
                    "duration_seconds": self.duration_threshold
                }
            },
            "violations": self.violations
        }

    def save_report(self) -> None:
        """Save the analysis report to a JSON file."""
        if any(self.violations.values()):
            try:
                report = self.generate_report()
                report_path = os.path.join(self.output_dir, "threshold_report.json")
                
                with open(report_path, "w") as f:
                    json.dump(report, f, indent=2)
                    
                logger.info(f"\nDetailed report saved to: {report_path}")
                
            except Exception as e:
                logger.error(f"Error saving report: {str(e)}")

    def run(self) -> None:
        """Execute threshold checking on collected metrics."""
        logger.info(
            f"Starting threshold analysis:"
            f"\n  Duration Threshold: {self.duration_threshold} seconds"
        )
        
        memory_file = os.path.join(self.output_dir, "memory_metrics.csv")
        cpu_file = os.path.join(self.output_dir, "cpu_metrics.csv")
        
        self.check_thresholds(memory_file, "Memory")
        self.check_thresholds(cpu_file, "CPU")
        
        if any(self.violations.values()):
            self.save_report()
        else:
            logger.info("No threshold violations detected.")


if __name__ == "__main__":
    output_dir = os.getenv('OUTPUT_DIR', 'output')
    logger.info(f"Using output directory: {output_dir}")
    
    # Dynamically load thresholds
    pod_thresholds = load_thresholds()
    
    if pod_thresholds:
        checker = ThresholdChecker(
            output_dir=output_dir,
            duration_threshold=10,           # 10 seconds
            pod_thresholds=pod_thresholds
        )
        checker.run()
    else:
        logger.error("Failed to retrieve updated thresholds. Exiting.")
