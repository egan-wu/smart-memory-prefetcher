#!/usr/bin/env python3
import torch
from pathlib import Path

def generate_cpp_array(name, tensor):
    flat_data = tensor.flatten().cpu().numpy()
    lines = [f"constexpr std::array<float, {len(flat_data)}> {name} = {{"]
    current_line = []
    for i, val in enumerate(flat_data):
        current_line.append(f"{val}f")
        if (i + 1) % 8 == 0:
            lines.append("    " + ", ".join(current_line) + ",")
            current_line = []
    if current_line: lines.append("    " + ", ".join(current_line))
    if lines[-1].endswith(","): lines[-1] = lines[-1][:-1]
    lines.append("};")
    return "\n".join(lines)

def export():
    state_dict = torch.load("weights/model_weights.pth", map_location='cpu')
    out_lines = ["#ifndef RL_PREFETCHER_WEIGHTS_H\n#define RL_PREFETCHER_WEIGHTS_H\n#include <array>\nnamespace rl_prefetcher_namespace {\n"]
    layer_idx = 1
    for key, tensor in state_dict.items():
        if "weight" in key:
            out_lines.append(generate_cpp_array(f"layer{layer_idx}_weights", tensor))
        elif "bias" in key:
            out_lines.append(generate_cpp_array(f"layer{layer_idx}_bias", tensor))
            layer_idx += 1
    out_lines.append("} \n#endif")
    with open("ChampSim/prefetcher/rl_prefetcher/weights.h", 'w') as f:
        f.write("\n".join(out_lines))

if __name__ == "__main__":
    Path("ChampSim/prefetcher/rl_prefetcher").mkdir(parents=True, exist_ok=True)
    export()
