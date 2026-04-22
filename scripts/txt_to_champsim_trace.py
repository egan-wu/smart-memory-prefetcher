#!/usr/bin/env python3
"""
txt_to_champsim_trace.py — Convert textual memory access logs to ChampSim traces.

Usage example with Valgrind Lackey:
  valgrind --tool=lackey --trace-mem=yes ./my_game_executable 2>&1 | python3 txt_to_champsim_trace.py --out traces/my_game.champsimtrace.gz

Valgrind Lackey output format looks like:
  I  04000100,4    (Instruction fetch)
  L  04000104,8    (Load)
  S  04000108,4    (Store)
  M  0400010C,8    (Modify: Load + Store)
"""

import sys
import struct
import gzip
import argparse
from pathlib import Path

# ChampSim Record Format: 1 IP (8b), 2 bools (2b), 6 bytes padding, 2 Dest (16b), 2 Src (16b) = 48 bytes
RECORD_FMT = "<Q BB 6x QQ QQ"
RECORD_SIZE = struct.calcsize(RECORD_FMT)

def make_record(ip: int, dest: list, src: list, is_branch=0, taken=0) -> bytes:
    d0, d1 = (dest + [0, 0])[:2]
    s0, s1 = (src  + [0, 0])[:2]
    return struct.pack(RECORD_FMT, ip, is_branch, taken, d0, d1, s0, s1)

def convert_trace(input_stream, output_file, max_instructions=10_000_000):
    print(f"Reading from input stream. Converting to {output_file}...")

    with gzip.open(output_file, "wb") as f_out:
        count = 0
        current_ip = 0
        current_loads = []
        current_stores = []

        # Simple state machine to accumulate loads/stores under the same Instruction Pointer (IP)
        for line in input_stream:
            line = line.strip()
            if not line: continue

            # Valgrind Lackey format parsing
            if line.startswith("I "):
                # Flush the previous instruction record if exists
                if current_ip != 0 and (current_loads or current_stores):
                    f_out.write(make_record(current_ip, current_loads, current_stores))
                    count += 1
                    if count >= max_instructions:
                        break
                    if count % 1000000 == 0:
                        print(f"Processed {count} instructions...")

                # Start new instruction
                current_loads = []
                current_stores = []
                try:
                    parts = line.split(" ", 1)[1].strip().split(",")
                    current_ip = int(parts[0], 16)
                except:
                    current_ip = 0

            elif line.startswith("L "):
                try:
                    parts = line.split(" ", 1)[1].strip().split(",")
                    addr = int(parts[0], 16)
                    current_loads.append(addr)
                except: pass

            elif line.startswith("S "):
                try:
                    parts = line.split(" ", 1)[1].strip().split(",")
                    addr = int(parts[0], 16)
                    current_stores.append(addr)
                except: pass

            elif line.startswith("M "):
                try:
                    parts = line.split(" ", 1)[1].strip().split(",")
                    addr = int(parts[0], 16)
                    current_loads.append(addr)
                    current_stores.append(addr)
                except: pass

        # Flush the last one
        if current_ip != 0 and (current_loads or current_stores) and count < max_instructions:
            f_out.write(make_record(current_ip, current_loads, current_stores))
            count += 1

    print(f"Done! Converted {count} instructions.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Valgrind/Text trace to ChampSim trace")
    parser.add_argument("--out", type=str, required=True, help="Output .champsimtrace.gz file")
    parser.add_argument("--max_inst", type=int, default=10000000, help="Max instructions to process")
    parser.add_argument("--input", type=str, default="-", help="Input text file (or '-' for stdin)")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.input == "-":
        if sys.stdin.isatty():
            print("Warning: Waiting for input from stdin... (Press Ctrl+D when done)")
        convert_trace(sys.stdin, args.out, args.max_inst)
    else:
        with open(args.input, "r") as f_in:
            convert_trace(f_in, args.out, args.max_inst)
