#!/usr/bin/env python3
"""
generate_synthetic_trace.py — Generate a synthetic ChampSim binary trace for testing.

ChampSim trace format (per instruction, 64 bytes total):
  uint8_t  is_branch
  uint8_t  branch_taken
  uint64_t destination_memory[2]   (load addresses)
  uint64_t source_memory[2]        (store addresses)
  uint64_t ip                      (instruction pointer)

The synthetic trace simulates irregular memory access patterns typical of
game workloads: streaming arrays, random graph traversals, and sparse accesses.
"""

import struct
import random
import gzip
import argparse
from pathlib import Path

RECORD_FMT = "<BB" + "QQ" + "QQ" + "Q"  # 1+1+8+8+8+8+8 = 42 bytes... ChampSim uses padded struct
# Actual ChampSim trace: see tracer/pin/champsim_tracer.cpp
# struct {
#   unsigned long long ip;        // 8 bytes
#   unsigned char is_branch;      // 1 byte
#   unsigned char branch_taken;   // 1 byte
#   unsigned char pad[6];         // 6 bytes padding
#   unsigned long long dest[2];   // 16 bytes
#   unsigned long long src[2];    // 16 bytes
# } = 48 bytes per record

RECORD_FMT = "<Q BB 6x QQ QQ"  # little-endian: ip, is_branch, branch_taken, pad, dest[2], src[2]
RECORD_SIZE = struct.calcsize(RECORD_FMT)  # should be 48 bytes

def make_record(ip: int, dest: list, src: list, is_branch=0, taken=0) -> bytes:
    d0, d1 = (dest + [0, 0])[:2]
    s0, s1 = (src  + [0, 0])[:2]
    return struct.pack(RECORD_FMT, ip, is_branch, taken, d0, d1, s0, s1)

def generate_trace(n_instructions: int, seed: int = 42) -> list[bytes]:
    """Generate a mixed-access pattern trace:
    - 40%: sequential streaming (good for next_line)
    - 30%: stride-2 access (good for ip_stride)
    - 30%: irregular/random access (hard for all prefetchers — simulates game data)
    """
    rng = random.Random(seed)
    records = []

    BASE_ADDR  = 0x100000000
    ARRAY_SIZE = 1 << 20  # 1M entries × 8 bytes = 8MB working set (fits in 4MB LLC with pressure)
    CACHE_LINE = 64

    ip = 0x400000
    stream_ptr  = BASE_ADDR
    stride_ptr  = BASE_ADDR + 0x1000000
    irregular_base = BASE_ADDR + 0x2000000

    for i in range(n_instructions):
        r = rng.random()

        if r < 0.40:
            # Sequential stream
            addr = stream_ptr
            stream_ptr += CACHE_LINE
            if stream_ptr > BASE_ADDR + ARRAY_SIZE * 8:
                stream_ptr = BASE_ADDR
            records.append(make_record(ip, [addr], []))

        elif r < 0.70:
            # Stride-2 pattern
            addr = stride_ptr
            stride_ptr += 2 * CACHE_LINE
            if stride_ptr > BASE_ADDR + 0x1000000 + ARRAY_SIZE * 16:
                stride_ptr = BASE_ADDR + 0x1000000
            records.append(make_record(ip + 4, [addr], []))

        else:
            # Irregular/random — simulates pointer chasing in game scene graph
            idx = rng.randint(0, (ARRAY_SIZE // 4) - 1)
            addr = irregular_base + idx * 8
            records.append(make_record(ip + 8, [addr], []))

        ip += rng.choice([4, 4, 4, 8])  # mostly 4-byte instructions

    return records


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic ChampSim trace")
    parser.add_argument("--output", default="traces/synthetic_game.champsimtrace.gz",
                        help="Output trace file path (.gz for compressed)")
    parser.add_argument("--instructions", type=int, default=5_000_000,
                        help="Number of instructions to generate")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.instructions:,} instruction trace → {out_path}")
    records = generate_trace(args.instructions, seed=args.seed)

    with gzip.open(out_path, "wb") as f:
        for rec in records:
            f.write(rec)

    size_mb = out_path.stat().st_size / 1e6
    print(f"Done. File size: {size_mb:.1f} MB  ({RECORD_SIZE} bytes/record)")


if __name__ == "__main__":
    main()
