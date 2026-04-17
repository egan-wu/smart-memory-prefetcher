#!/usr/bin/env python3
"""
export_weights.py — Task 4: Export PyTorch Weights to C++ Headers

Reads the trained model weights and writes them out as `constexpr std::array`
in a C++ header file. This allows the ChampSim inference engine to compile
the weights directly into the binary, mimicking SRAM-baked weights in ASIC.
"""

import torch
import argparse
from pathlib import Path

def generate_cpp_array(name, tensor, cols_per_line=8):
    """Converts a PyTorch tensor into a formatted C++ std::array string."""
    flat_data = tensor.flatten().cpu().numpy()
    cpp_type = f"std::array<float, {len(flat_data)}>"

    lines = []
    lines.append(f"constexpr {cpp_type} {name} = {{")

    current_line = []
    for i, val in enumerate(flat_data):
        current_line.append(f"{val}f")
        if (i + 1) % cols_per_line == 0:
            lines.append("    " + ", ".join(current_line) + ",")
            current_line = []

    if current_line:
        lines.append("    " + ", ".join(current_line))

    # Remove the trailing comma from the very last line if present
    if lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]

    lines.append("};")
    return "\n".join(lines)

def export(model_path, out_path):
    print(f"Loading weights from {model_path}...")
    state_dict = torch.load(model_path, map_location='cpu')

    out_lines = [
        "#ifndef RL_PREFETCHER_WEIGHTS_H",
        "#define RL_PREFETCHER_WEIGHTS_H",
        "",
        "#include <array>",
        "",
        "namespace rl_prefetcher {",
        ""
    ]

    layer_idx = 1
    for key, tensor in state_dict.items():
        if "weight" in key:
            # PyTorch stores Linear weights as (out_features, in_features).
            # For standard C++ matrix multiplication (X * W^T), we might need to transpose.
            # However, PyTorch's F.linear does Y = XW^T + b.
            # We will transpose it here so C++ can just do standard dot products easily.
            # If tensor is (out, in), we transpose to (in, out) if we do X * W.
            # Actually, standard matrix-vector in C++ is usually dot product of row.
            # We'll just export it as is (out, in) and handle the layout in C++.
            name = f"layer{layer_idx}_weights"
            print(f"Exporting {name} | shape: {tensor.shape}")
            out_lines.append(f"// Shape: {list(tensor.shape)}")
            out_lines.append(generate_cpp_array(name, tensor))
            out_lines.append("")
        elif "bias" in key:
            name = f"layer{layer_idx}_bias"
            print(f"Exporting {name} | shape: {tensor.shape}")
            out_lines.append(f"// Shape: {list(tensor.shape)}")
            out_lines.append(generate_cpp_array(name, tensor))
            out_lines.append("")
            layer_idx += 1

    out_lines.append("} // namespace rl_prefetcher")
    out_lines.append("")
    out_lines.append("#endif // RL_PREFETCHER_WEIGHTS_H")

    with open(out_path, 'w') as f:
        f.write("\n".join(out_lines))

    print(f"\nSuccessfully exported C++ header to {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="weights/model_weights.pth")
    parser.add_argument("--out", type=str, default="ChampSim/prefetcher/rl_prefetcher/weights.h")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Error: Model file {model_path} not found.")
        exit(1)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    export(args.model, args.out)