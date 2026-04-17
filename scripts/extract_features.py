#!/usr/bin/env python3
"""
extract_features.py — Task 2: Feature Extraction for RL Prefetcher

Reads a ChampSim trace (or trace records) and converts them into structured ML data
(State-Action pairs) using a sliding window of address deltas per PC hash.
This generates the offline training data for the DQN/MLP.

State: PC_Hash + [Delta_t-N, ..., Delta_t-1]
Action: Delta_t (target to predict, offset relative to the current cache line)
"""

import struct
import gzip
import argparse
import numpy as np
from collections import defaultdict
from pathlib import Path

# Same record format as generate_synthetic_trace.py
RECORD_FMT = "<Q BB 6x QQ QQ"
RECORD_SIZE = struct.calcsize(RECORD_FMT)
CACHE_LINE_BITS = 6  # 64-byte cache line

def pc_hash(ip):
    """Simple hash for Program Counter to reduce dimensionality (similar to hardware)."""
    return (ip ^ (ip >> 2) ^ (ip >> 5)) & 0x3FF  # 10-bit hash (1024 unique PCs)

def process_trace(trace_file, window_size=8, max_delta=4, output_file=None):
    """
    Reads a ChampSim trace and extracts sliding window features for training.
    """
    print(f"Reading trace: {trace_file}")

    # Per-PC history buffer: pc -> list of recent block addresses
    history_per_pc = defaultdict(list)

    # Store extracted features: [PC_Hash, D_t-7, D_t-6, ..., D_t-1]
    # Store labels: Action (the next Delta_t clamped to valid action space)
    X = []
    y = []

    # Map delta to discrete action class
    # Actions: 0 (No prefetch), 1 (+1), 2 (+2), 3 (-1), 4 (-2), etc.
    # In a real model, we might limit it to a few options.
    def delta_to_action(delta):
        if delta == 0:
            return 0 # Should not happen usually as consecutive hits to same cacheline are filtered
        # Simple mapping for offsets in [-max_delta, max_delta]
        if -max_delta <= delta <= max_delta:
            # Action 0 is 'None'. So we map valid deltas to 1..2*max_delta
            if delta > 0:
                return delta
            else:
                return max_delta + abs(delta)
        return 0 # Out of bounds -> Action 0 (Do nothing)

    with gzip.open(trace_file, 'rb') as f:
        count = 0
        while True:
            chunk = f.read(RECORD_SIZE)
            if not chunk or len(chunk) < RECORD_SIZE:
                break

            ip, is_branch, branch_taken, d0, d1, s0, s1 = struct.unpack(RECORD_FMT, chunk)

            # We only care about load memory accesses
            if d0 == 0:
                continue

            block_addr = d0 >> CACHE_LINE_BITS
            h_pc = pc_hash(ip)
            hist = history_per_pc[h_pc]

            # Hardware L1 Cache filter: Avoid consecutive accesses to the same cache line.
            # We must ignore these completely before processing any sliding windows.
            if hist and hist[-1] == block_addr:
                continue

            # If we have enough history to form a state AND a target action
            if len(hist) == window_size + 1:
                # Calculate deltas for the state
                state_deltas = []
                for i in range(1, window_size + 1):
                    d = hist[i] - hist[i-1]
                    # Clamp state deltas to a reasonable range for neural net inputs
                    d_clamped = max(min(d, 127), -128)
                    state_deltas.append(d_clamped)

                # The target action is the delta from the last state to the current block
                target_delta = block_addr - hist[-1]
                action = delta_to_action(target_delta)

                # We only want to learn non-zero actions or explicit zero actions where appropriate
                # To balance the dataset, we might filter some. For now, keep all.
                X.append([h_pc] + state_deltas)
                y.append(action)

                # Pop oldest
                hist.pop(0)

            # Add current to history.
            hist.append(block_addr)

            count += 1
            if count % 1000000 == 0:
                print(f"Processed {count} memory accesses...")

    X = np.array(X, dtype=np.int32)
    y = np.array(y, dtype=np.int32)

    print(f"Extraction complete. Total samples: {len(X)}")
    print(f"Action distribution: {np.bincount(y)}")

    if output_file:
        print(f"Saving to {output_file} ...")
        np.savez_compressed(output_file, X=X, y=y)
        print("Done.")

    return X, y


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=str, default="traces/synthetic_game.champsimtrace.gz", help="Path to input trace")
    parser.add_argument("--out", type=str, default="training_data.npz", help="Output .npz file")
    parser.add_argument("--window", type=int, default=8, help="Sliding window size N")
    args = parser.parse_args()

    trace_path = Path(args.trace)
    if not trace_path.exists():
        print(f"Error: Trace file {trace_path} not found. Please run generate_synthetic_trace.py first.")
        exit(1)

    process_trace(args.trace, window_size=args.window, output_file=args.out)
