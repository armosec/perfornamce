#!/usr/bin/env python3
"""
Compare before/after eBPF dedup benchmark metrics.

Usage: python3 compare-metrics.py <before-dir> <after-dir>

Reads cpu_metrics.csv, memory_metrics.csv, dedup_total.json, and events_total.json
produced by dedup-bench.sh and prints a side-by-side comparison table.
"""

import json
import sys
from pathlib import Path

import pandas as pd


def load_csv(directory: Path, name: str) -> pd.DataFrame:
    path = directory / name
    if not path.exists():
        print(f"Warning: {path} not found", file=sys.stderr)
        return pd.DataFrame(columns=["Time", "Pod", "Value"])
    return pd.read_csv(path)


def load_json(directory: Path, name: str) -> dict | None:
    path = directory / name
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def compute_resource_stats(df: pd.DataFrame) -> dict:
    """Filter to node-agent pods and compute avg/peak."""
    na = df[df["Pod"].str.contains("node-agent", na=False)]
    if na.empty:
        return {"avg": 0.0, "peak": 0.0}
    return {"avg": na["Value"].mean(), "peak": na["Value"].max()}


def format_delta(before: float, after: float) -> str:
    if before == 0:
        return "N/A"
    pct = (after - before) / before * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def print_resource_table(before_dir: Path, after_dir: Path) -> None:
    before_cpu = compute_resource_stats(load_csv(before_dir, "cpu_metrics.csv"))
    after_cpu = compute_resource_stats(load_csv(after_dir, "cpu_metrics.csv"))
    before_mem = compute_resource_stats(load_csv(before_dir, "memory_metrics.csv"))
    after_mem = compute_resource_stats(load_csv(after_dir, "memory_metrics.csv"))

    rows = [
        ("Avg CPU (cores)", before_cpu["avg"], after_cpu["avg"]),
        ("Peak CPU (cores)", before_cpu["peak"], after_cpu["peak"]),
        ("Avg Memory (MiB)", before_mem["avg"], after_mem["avg"]),
        ("Peak Memory (MiB)", before_mem["peak"], after_mem["peak"]),
    ]

    print("  Node-Agent Resource Usage")
    print("  " + "-" * 55)
    print(f"  {'Metric':<22}{'BEFORE':>12}{'AFTER':>12}{'Delta':>12}")
    print("  " + "-" * 55)
    for label, bv, av in rows:
        print(f"  {label:<22}{bv:>12.3f}{av:>12.3f}{format_delta(bv, av):>12}")
    print()


def print_dedup_table(after_dir: Path) -> None:
    data = load_json(after_dir, "dedup_total.json")
    if not data or data.get("status") != "success":
        print("  Dedup Effectiveness: no data available\n")
        return

    results = data.get("data", {}).get("result", [])
    if not results:
        print("  Dedup Effectiveness: no data available\n")
        return

    # Aggregate by event_type
    by_type: dict[str, dict[str, float]] = {}
    for item in results:
        et = item["metric"].get("event_type", "unknown")
        result = item["metric"].get("result", "unknown")
        value = float(item["value"][1]) if len(item.get("value", [])) > 1 else 0.0
        by_type.setdefault(et, {"passed": 0.0, "deduplicated": 0.0})
        by_type[et][result] = value

    print("  Dedup Effectiveness (AFTER only)")
    print("  " + "-" * 55)
    print(f"  {'Event Type':<16}{'Passed':>10}{'Deduped':>10}{'Ratio':>10}")
    print("  " + "-" * 55)
    for et in sorted(by_type):
        passed = by_type[et]["passed"]
        deduped = by_type[et]["deduplicated"]
        total = passed + deduped
        ratio = f"{deduped / total * 100:.1f}%" if total > 0 else "N/A"
        print(f"  {et:<16}{passed:>10.0f}{deduped:>10.0f}{ratio:>10}")
    print()


def print_event_comparison(before_dir: Path, after_dir: Path) -> None:
    before_data = load_json(before_dir, "events_total.json")
    after_data = load_json(after_dir, "events_total.json")

    def extract_counters(data: dict | None) -> dict[str, float]:
        if not data or data.get("status") != "success":
            return {}
        counters: dict[str, float] = {}
        for item in data.get("data", {}).get("result", []):
            name = item["metric"].get("__name__", "")
            # Sum across pods for each metric name
            value = float(item["value"][1]) if len(item.get("value", [])) > 1 else 0.0
            counters[name] = counters.get(name, 0.0) + value
        return counters

    before_counters = extract_counters(before_data)
    after_counters = extract_counters(after_data)
    all_names = sorted(set(before_counters) | set(after_counters))

    if not all_names:
        return

    print("  Event Counters")
    print("  " + "-" * 55)
    print(f"  {'Metric':<35}{'BEFORE':>10}{'AFTER':>10}")
    print("  " + "-" * 55)
    for name in all_names:
        bv = before_counters.get(name, 0.0)
        av = after_counters.get(name, 0.0)
        # Shorten metric name for display
        short = name.replace("node_agent_", "")
        print(f"  {short:<35}{bv:>10.0f}{av:>10.0f}")
    print()


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <before-dir> <after-dir>", file=sys.stderr)
        sys.exit(1)

    before_dir = Path(sys.argv[1])
    after_dir = Path(sys.argv[2])

    for d in (before_dir, after_dir):
        if not d.is_dir():
            print(f"Error: {d} is not a directory", file=sys.stderr)
            sys.exit(1)

    print()
    print("=" * 61)
    print("  eBPF Dedup Benchmark Results")
    print("=" * 61)
    print()

    print_resource_table(before_dir, after_dir)
    print_dedup_table(after_dir)
    print_event_comparison(before_dir, after_dir)

    print("=" * 61)
    print()


if __name__ == "__main__":
    main()
