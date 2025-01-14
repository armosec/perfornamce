import requests
from datetime import datetime, timedelta, timezone
import pandas as pd
import matplotlib.pyplot as plt
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PrometheusConfig:
    url: str = "http://localhost:9090"
    namespace: str = "kubescape"
    pod_regex: str = "node-agent.*"
    time_window_hours: int = 5
    step_minutes: str = "1"

class PrometheusMetricsCollector:
    def __init__(self, config: Optional[PrometheusConfig] = None):
        self.config = config or PrometheusConfig()
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(hours=self.config.time_window_hours)
        
    def query_prometheus_range(self, query: str) -> Optional[List[Dict]]:
        """Execute a Prometheus range query with error handling."""
        params = {
            'query': query,
            'start': self.start_time.isoformat(),
            'end': self.end_time.isoformat(),
            'step': f"{self.config.step_minutes}m"
        }
        
        try:
            logger.info(f"Querying Prometheus with: {query}")
            response = requests.get(
                f'{self.config.url}/api/v1/query_range',
                params=params,
                timeout=30  # Add timeout
            )
            response.raise_for_status()
            
            data = response.json()
            if 'data' in data and 'result' in data['data']:
                return data['data']['result']
            else:
                logger.warning("No data found for the query")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying Prometheus: {str(e)}")
            return None
            
    def process_metrics(self, metrics: List[Dict], metric_type: str) -> pd.DataFrame:
        """Process metrics into a DataFrame with better type handling."""
        if not metrics:
            return pd.DataFrame(columns=['Time', 'Pod', 'Value'])
            
        all_data = []
        for item in metrics:
            pod = item['metric'].get('pod', 'unknown')
            for timestamp, value in item['values']:
                try:
                    timestamp_readable = datetime.fromtimestamp(float(timestamp), timezone.utc)
                    value = float(value)
                    if metric_type == "Memory":
                        value = value / (1024 ** 2)  # Convert to MiB
                    all_data.append({
                        'Time': timestamp_readable,
                        'Pod': pod,
                        'Value': value
                    })
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing metric value: {str(e)}")
                    continue
                    
        return pd.DataFrame(all_data)

    def filter_zero_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter out negative values and handle NaN values."""
        df['Value'] = pd.to_numeric(df['Value'], errors='coerce')
        return df[df['Value'].notna() & (df['Value'] >= 0)]

    def plot_individual(self, df: pd.DataFrame, metric_type: str) -> None:
        """Create plots with improved styling and error handling."""
        if df.empty:
            logger.warning(f"No data to plot for {metric_type}")
            return
            
        plt.style.use('bmh')
            
        for pod, pod_data in df.groupby('Pod'):
            try:
                plt.figure(figsize=(12, 6))
                
                plt.plot(pod_data['Time'], pod_data['Value'],
                        label=pod, marker='o', linestyle='-', markersize=4)
                
                plt.title(f"{metric_type} Usage Over Time\nPod: {pod}", fontsize=16)
                plt.xlabel("Time (UTC)", fontsize=12)
                plt.ylabel(f"{metric_type} ({'MiB' if metric_type == 'Memory' else 'Cores'})",
                         fontsize=12)
                
                plt.grid(True, linestyle='--', alpha=0.7)
                plt.xticks(rotation=45)
                plt.tight_layout()
                
                filename = f"{pod}_{metric_type.lower()}_usage.png"
                plt.savefig(filename, dpi=300, bbox_inches='tight')
                logger.info(f"Saved graph: {filename}")
                plt.close()
                
            except Exception as e:
                logger.error(f"Error creating plot for pod {pod}: {str(e)}")
                plt.close()

    def save_to_csv(self, df: pd.DataFrame, metric_type: str) -> None:
        """Save data to CSV with error handling."""
        if df.empty:
            logger.warning(f"No data to save for {metric_type}")
            return
            
        try:
            filename = f"{metric_type.lower()}_metrics.csv"
            df.to_csv(filename, index=False)
            logger.info(f"Saved data to CSV: {filename}")
        except Exception as e:
            logger.error(f"Error saving CSV file: {str(e)}")

    def run(self):
        """Main execution method with improved memory query."""
        # Memory Query - Modified to be more specific
        memory_query = (
            f'container_memory_working_set_bytes{{namespace="{self.config.namespace}",'
            f'pod=~"{self.config.pod_regex}", container!="", container!="POD"}}'
        )
        memory_results = self.query_prometheus_range(memory_query)

        # Debug memory results
        if memory_results:
            logger.info("Memory query returned results:")
            for result in memory_results:
                logger.info(f"Metric labels: {result['metric']}")

        # CPU Query
        cpu_query = (
            f'sum(rate(container_cpu_usage_seconds_total{{namespace="{self.config.namespace}",'
            f'pod=~"{self.config.pod_regex}"}}[5m])) by (pod)'
        )
        cpu_results = self.query_prometheus_range(cpu_query)

        # Process Memory metrics
        if memory_results:
            memory_df = self.process_metrics(memory_results, "Memory")
            logger.info(f"Unique pods in memory data: {memory_df['Pod'].unique()}")
            logger.info(f"Memory value ranges: \n{memory_df.groupby('Pod')['Value'].describe()}")
            
            memory_df = self.filter_zero_values(memory_df)
            self.save_to_csv(memory_df, "Memory")
            self.plot_individual(memory_df, "Memory")

        # Process CPU metrics
        if cpu_results:
            cpu_df = self.process_metrics(cpu_results, "CPU")
            cpu_df = self.filter_zero_values(cpu_df)
            self.save_to_csv(cpu_df, "CPU")
            self.plot_individual(cpu_df, "CPU")

if __name__ == "__main__":
    # Create collector with default configuration
    collector = PrometheusMetricsCollector()
    collector.run()