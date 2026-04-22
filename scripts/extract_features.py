#!/usr/bin/env python3
import struct
import gzip
import argparse
import numpy as np
from collections import defaultdict
from pathlib import Path

RECORD_FMT = "<Q BB 6x QQ QQ"
RECORD_SIZE = struct.calcsize(RECORD_FMT)
CACHE_LINE_BITS = 6

def pc_hash(ip):
    return (ip ^ (ip >> 2) ^ (ip >> 5)) & 0x3FF

def process_trace(trace_file, window_size=8, max_delta=4, output_file=None):
    history_per_pc = defaultdict(list)
    X = []
    y = []

    def delta_to_action(delta):
        if delta == 0: return 0
        if -max_delta <= delta <= max_delta:
            if delta > 0: return delta
            else: return max_delta + abs(delta)
        return 0

    with gzip.open(trace_file, 'rb') as f:
        while True:
            chunk = f.read(RECORD_SIZE)
            if not chunk or len(chunk) < RECORD_SIZE: break
            ip, is_branch, branch_taken, d0, d1, s0, s1 = struct.unpack(RECORD_FMT, chunk)
            if d0 == 0: continue

            block_addr = d0 >> CACHE_LINE_BITS
            h_pc = pc_hash(ip)
            hist = history_per_pc[h_pc]

            if hist and hist[-1] == block_addr:
                continue

            if len(hist) == window_size + 1:
                state_deltas = []
                for i in range(1, window_size + 1):
                    d = hist[i] - hist[i-1]
                    d_clamped = max(min(d, 127), -128)
                    state_deltas.append(d_clamped)
                target_delta = block_addr - hist[-1]
                action = delta_to_action(target_delta)
                X.append([h_pc] + state_deltas)
                y.append(action)
                hist.pop(0)

            hist.append(block_addr)

    X = np.array(X, dtype=np.int32)
    y = np.array(y, dtype=np.int32)
    if output_file:
        np.savez_compressed(output_file, X=X, y=y)

if __name__ == "__main__":
    import sys; process_trace(sys.argv[1] if len(sys.argv) > 1 else "traces/synthetic_game.champsimtrace.gz", output_file=sys.argv[2] if len(sys.argv) > 2 else "training_data.npz")
