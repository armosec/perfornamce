import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any
import numpy as np

def analyze_profile_data(data: Dict[Any, Any]):
    """
    Analyzes profiling data to create a top table and flamegraph visualization.
    Values are displayed in MiB.
    
    Args:
        data: Dictionary containing the profiling data with 'flamebearer' section
        
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
    
    # Sort by Self_MiB
    df = df.sort_values('Self_MiB', ascending=False).reset_index(drop=True)
    
    # Round values for display
    df['Total_MiB'] = df['Total_MiB'].round(2)
    df['Self_MiB'] = df['Self_MiB'].round(2)
    df['Self_Percentage'] = df['Self_Percentage'].round(2)
    df['Total_Percentage'] = df['Total_Percentage'].round(2)
    
    # Select and reorder columns for display
    display_df = df[[
        'Function',
        'Self_MiB',
        'Total_MiB',
        'Self_Percentage',
        'Total_Percentage'
    ]]
    
    # Create flamegraph
    fig = create_flamegraph(levels, names, total_ticks)
    
    return display_df.head(20), fig

def create_flamegraph(levels: list, names: list, total_ticks: int) -> go.Figure:
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
        title='Memory Usage Flamegraph (MiB)',
        xaxis_title='Memory Usage (MiB)',
        yaxis_title='Stack Depth',
        barmode='stack',
        bargap=0,
        bargroupgap=0,
        height=800,
        yaxis=dict(autorange="reversed")
    )
    
    return fig

def process_profile(json_data: Dict[Any, Any], output_csv: str = "profile_results.csv", output_html: str = "profile_flamegraph.html"):
    """
    Process the profile data, print results, and save to CSV and HTML.
    
    Args:
        json_data: The parsed JSON profile data
        output_csv: Path to save the CSV file (default: "profile_results.csv")
        output_html: Path to save the flamegraph HTML file (default: "profile_flamegraph.html")
    """
    top_table, flamegraph = analyze_profile_data(json_data)
    
    print("\nTop 20 Functions by Self Memory Usage (MiB):")
    print(top_table.to_string(index=False))
    
    # Save to CSV
    top_table.to_csv(output_csv, index=False)
    print(f"\nResults saved to: {output_csv}")
    
    # Save flamegraph to HTML
    flamegraph.write_html(output_html)
    print(f"Flamegraph saved to: {output_html}")
    
    return top_table, flamegraph

if __name__ == "__main__":
    import json
    
    # Read the JSON file
    with open('pyroscope_profile_data.json', 'r') as f:
        json_data = json.load(f)
    
    # Process the profile data
    top_table, flamegraph = process_profile(json_data)
    
    # Display the flamegraph
    flamegraph.show()