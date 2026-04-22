#!/usr/bin/env python3
"""
parse_results.py — Parse ChampSim simulation output logs and produce baseline_results.csv

Metrics extracted per simulation:
  - IPC  : Instructions Per Cycle (higher is better)
  - MPKI : LLC Misses Per Kilo Instructions (lower is better)
  - DRAM_BW_GBs : Estimated DRAM bandwidth usage (GB/s)

Usage:
    python3 scripts/parse_results.py [--results-dir ./results] [--output ./baseline_results.csv]
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns for ChampSim output fields
# ──────────────────────────────────────────────────────────────────────────────

RE_IPC = re.compile(r"CPU\s+\d+\s+cumulative\s+IPC[:\s]+([0-9.]+)", re.IGNORECASE)
RE_INSTRUCTIONS = re.compile(r"Finished\s+CPU\s+\d+.*?Instructions:\s+(\d+)", re.IGNORECASE)

# LLC miss stats — ChampSim prints a table per cache; we want LLC LOAD MISS
RE_LLC_MISS = re.compile(
    r"LLC\s+LOAD\s+ACCESS.*?MISS\s+(\d+)", re.IGNORECASE
)
# Alternative pattern for newer ChampSim format
RE_LLC_MISS_ALT = re.compile(
    r"cpu\s+\d+\s+LLC\s+load\s+misses[:\s]+(\d+)", re.IGNORECASE
)

RE_DRAM_RD = re.compile(
    r"DRAM.*?RQ.*?ROW_BUFFER_HIT\s*:\s*\d+\s+ROW_BUFFER_MISS\s*:\s*\d+", re.IGNORECASE
)
# Bandwidth: some versions print "avg bandwidth" in GB/s
RE_DRAM_BW = re.compile(r"Average\s+bandwidth.*?([0-9.]+)\s*GB", re.IGNORECASE)
# Fallback: total DRAM accesses + simulation time → derive BW
RE_DRAM_CYCLES = re.compile(r"DRAM.*?cycles\s*[:=]\s*(\d+)", re.IGNORECASE)
RE_DRAM_TOTAL = re.compile(r"DRAM.*?total\s+accesses\s*[:=]\s*(\d+)", re.IGNORECASE)
RE_CPU_FREQ = re.compile(r"CPU Frequency[:\s]+(\d+)\s*MHz", re.IGNORECASE)


def parse_log(filepath: Path) -> dict:
    """Parse a single ChampSim log file and return a dict of metrics."""
    text = filepath.read_text(errors="replace")
    result = {
        "trace": filepath.stem,
        "config": filepath.parent.name,
        "IPC": None,
        "LLC_MPKI": None,
        "DRAM_BW_GBs": None,
    }

    # IPC
    m = RE_IPC.search(text)
    if m:
        result["IPC"] = float(m.group(1))

    # Instructions (for MPKI denominator)
    instr = None
    for pat in [
        re.compile(r"Finished\s+CPU\s+\d+\s+instructions:\s+(\d+)", re.IGNORECASE),
        re.compile(r"CPU\s+\d+\s+cumulative\s+IPC.*?instructions:\s+(\d+)", re.IGNORECASE),
        re.compile(r"(\d+)\s+instructions", re.IGNORECASE),
    ]:
        m2 = pat.search(text)
        if m2:
            instr = int(m2.group(1))
            break

    # LLC load misses
    llc_miss = None
    for pat in [RE_LLC_MISS, RE_LLC_MISS_ALT]:
        m3 = pat.search(text)
        if m3:
            llc_miss = int(m3.group(1))
            break

    # Compute MPKI = LLC_load_misses / (instructions / 1000)
    if llc_miss is not None and instr and instr > 0:
        result["LLC_MPKI"] = round(llc_miss / (instr / 1000.0), 4)

    # DRAM bandwidth
    m4 = RE_DRAM_BW.search(text)
    if m4:
        result["DRAM_BW_GBs"] = float(m4.group(1))

    return result


def collect_logs(results_dir: Path) -> list[dict]:
    rows = []
    for config_dir in sorted(results_dir.iterdir()):
        if not config_dir.is_dir():
            continue
        for log_file in sorted(config_dir.glob("*.txt")):
            row = parse_log(log_file)
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description="Parse ChampSim results into CSV")
    parser.add_argument("--results-dir", default="results", help="Directory containing simulation output subdirs")
    parser.add_argument("--output", default="baseline_results.csv", help="Output CSV file path")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"[ERROR] Results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    rows = collect_logs(results_dir)
    if not rows:
        print("[WARN] No log files found. Run scripts/run_baseline.sh first.")
        sys.exit(0)

    fieldnames = ["trace", "config", "IPC", "LLC_MPKI", "DRAM_BW_GBs"]
    output_path = Path(args.output)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")

    # Print summary table
    print(f"\n{'Trace':<30} {'Config':<12} {'IPC':>8} {'MPKI':>10} {'BW(GB/s)':>10}")
    print("-" * 75)
    for r in rows:
        ipc_s  = f"{r['IPC']:.4f}"   if r['IPC']        is not None else "N/A"
        mpki_s = f"{r['LLC_MPKI']:.4f}" if r['LLC_MPKI'] is not None else "N/A"
        bw_s   = f"{r['DRAM_BW_GBs']:.2f}" if r['DRAM_BW_GBs'] is not None else "N/A"
        print(f"{r['trace']:<30} {r['config']:<12} {ipc_s:>8} {mpki_s:>10} {bw_s:>10}")


if __name__ == "__main__":
    main()
