import os
import json
import pandas as pd
import plotly.graph_objects as go # type: ignore
from typing import Dict, Any
import glob
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_profile_data(data: Dict[Any, Any], pod_name: str):
    """
    Analyzes profiling data to create a top table and flamegraph visualization.
    Values are displayed in MiB.
    
    Args:
        data: Dictionary containing the profiling data with 'flamebearer' section
        pod_name: Name of the pod being analyzed
        
    Returns:
        tuple: (DataFrame with top functions, Plotly figure with flamegraph)
    """
    names = data['flamebearer']['names']
    levels = data['flamebearer']['levels']
    total_ticks = data['flamebearer']['numTicks']
    
    # Create dictionary to store function statistics
    function_stats = {}
    
    # Process each level to find function stats
    for level in levels:
        for i in range(0, len(level), 4):
            if i + 3 < len(level):
                pos = level[i]
                total_ticks = level[i + 1]
                self_ticks = level[i + 2]  # This is the self ticks value
                name_idx = level[i + 3]
                
                if name_idx < len(names):
                    func_name = names[name_idx]
                    if func_name not in function_stats:
                        function_stats[func_name] = {
                            'Function': func_name,
                            'Total_Ticks': 0,
                            'Self_Ticks': 0
                        }
                    
                    function_stats[func_name]['Total_Ticks'] += total_ticks
                    function_stats[func_name]['Self_Ticks'] += self_ticks if self_ticks else 0
    
    # Create DataFrame
    df = pd.DataFrame(list(function_stats.values()))
    
    # Convert ticks to MiB (assuming 1 tick = 1 byte)
    BYTES_TO_MIB = 1 / (1024 * 1024)
    df['Total_MiB'] = df['Total_Ticks'] * BYTES_TO_MIB
    df['Self_MiB'] = df['Self_Ticks'] * BYTES_TO_MIB
    
    # Calculate percentages
    df['Self_Percentage'] = (df['Self_Ticks'] / total_ticks * 100)
    df['Total_Percentage'] = (df['Total_Ticks'] / total_ticks * 100)
    
    # Add pod name column
    df['Pod'] = pod_name
    
    # Sort by Self_MiB
    df = df.sort_values('Self_MiB', ascending=False).reset_index(drop=True)
    
    # Round values for display
    df['Total_MiB'] = df['Total_MiB'].round(2)
    df['Self_MiB'] = df['Self_MiB'].round(2)
    df['Self_Percentage'] = df['Self_Percentage'].round(2)
    df['Total_Percentage'] = df['Total_Percentage'].round(2)
    
    # Select and reorder columns for display
    display_df = df[[
        'Pod',
        'Function',
        'Self_MiB',
        'Total_MiB',
        'Self_Percentage',
        'Total_Percentage'
    ]]
    
    # Create flamegraph
    fig = create_flamegraph(levels, names, total_ticks, pod_name)
    
    return display_df.head(20), fig

def create_flamegraph(levels: list, names: list, total_ticks: int, pod_name: str) -> go.Figure:
    """
    Creates a flamegraph visualization using Plotly.
    Values are displayed in MiB.
    """
    BYTES_TO_MIB = 1 / (1024 * 1024)
    
    x_starts = []
    x_ends = []
    y_levels = []
    function_names = []
    widths = []
    self_ticks = []
    
    for level_idx, level in enumerate(levels):
        x_position = 0
        
        for i in range(0, len(level), 4):
            if i + 3 < len(level):
                pos = level[i]
                width = level[i + 1]
                self_tick = level[i + 2] if i + 2 < len(level) else 0
                name_idx = level[i + 3]
                
                if width > 0 and name_idx < len(names):
                    x_starts.append(x_position)
                    x_ends.append(x_position + width)
                    y_levels.append(level_idx)
                    function_names.append(names[name_idx])
                    widths.append(width)
                    self_ticks.append(self_tick)
                
                x_position += width
    
    # Create hover text with MiB values
    hover_text = [
        f"{name}<br>Total: {(width * BYTES_TO_MIB):.2f} MiB ({(width/total_ticks*100):.2f}%)<br>Self: {(self_tick * BYTES_TO_MIB):.2f} MiB"
        for name, width, self_tick in zip(function_names, widths, self_ticks)
    ]
    
    # Create flamegraph
    fig = go.Figure(go.Bar(
        x=[(x_end - x_start) * BYTES_TO_MIB for x_start, x_end in zip(x_starts, x_ends)],
        y=y_levels,
        base=[x_start * BYTES_TO_MIB for x_start in x_starts],
        orientation='h',
        text=function_names,
        hovertext=hover_text,
        hoverinfo='text',
        marker=dict(
            color=[s for s in self_ticks],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title='Self MiB')
        ),
        showlegend=False
    ))
    
    # Update layout
    fig.update_layout(
        title=f'Memory Usage Flamegraph (MiB) - {pod_name}',
        xaxis_title='Memory Usage (MiB)',
        yaxis_title='Stack Depth',
        barmode='stack',
        bargap=0,
        bargroupgap=0,
        height=800,
        yaxis=dict(autorange="reversed")
    )
    
    return fig

def process_profile(json_data: Dict[Any, Any], pod_name: str, output_dir: str):
    """
    Process the profile data for a specific pod, save results to CSV and HTML.
    
    Args:
        json_data: The parsed JSON profile data
        pod_name: Name of the pod being analyzed
        output_dir: Directory to save results
    """
    os.makedirs(output_dir, exist_ok=True)
    output_csv = os.path.join(output_dir, f"profile_results_{pod_name}.csv")
    output_html = os.path.join(output_dir, f"profile_flamegraph_{pod_name}.html")
    
    top_table, flamegraph = analyze_profile_data(json_data, pod_name)
    
    print(f"\nTop 20 Functions by Self Memory Usage (MiB) for {pod_name}:")
    print(top_table.to_string(index=False))
    
    # Save to CSV
    top_table.to_csv(output_csv, index=False)
    logger.info(f"Results saved to: {output_csv}")
    
    # Save flamegraph to HTML
    flamegraph.write_html(output_html)
    logger.info(f"Flamegraph saved to: {output_html}")
    
    return top_table, flamegraph

def main():
    OUTPUT_DIR = "output"
    all_results = []
    
    # Find all profile data files
    profile_files = glob.glob(os.path.join(OUTPUT_DIR, "pyroscope_profile_data_node-agent-*.json"))
    
    if not profile_files:
        logger.error(f"No profile data files found in {OUTPUT_DIR}")
        return
    
    logger.info(f"Found {len(profile_files)} profile data files")
    
    # Process each profile file
    for profile_file in profile_files:
        pod_name = os.path.basename(profile_file).replace("pyroscope_profile_data_", "").replace(".json", "")
        
        try:
            with open(profile_file, 'r') as f:
                json_data = json.load(f)
            
            top_table, _ = process_profile(json_data, pod_name, OUTPUT_DIR)
            all_results.append(top_table)
            
        except Exception as e:
            logger.error(f"Error processing {profile_file}: {e}")
    
    # Combine all results into a single CSV
    if all_results:
        combined_results = pd.concat(all_results, ignore_index=True)
        combined_csv = os.path.join(OUTPUT_DIR, "combined_profile_results.csv")
        combined_results.to_csv(combined_csv, index=False)
        logger.info(f"Combined results saved to: {combined_csv}")

if __name__ == "__main__":
    main()