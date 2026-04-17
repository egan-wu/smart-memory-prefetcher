# RL-Based Smart Memory Prefetcher

A research project that replaces traditional hardware prefetchers with a lightweight Reinforcement Learning agent, targeting next-generation game console architectures.

---

## 1. Purpose

Modern game workloads generate highly irregular memory access patterns — pointer chasing, sparse asset streaming, dynamic scene graphs — that defeat conventional prefetchers like `next_line` and `ip_stride`. These prefetchers either cause **cache pollution** (fetching unused data) or simply miss the irregular accesses entirely, wasting precious DRAM bandwidth.

**Goal:** Design a minimal RL-based prefetch agent that learns per-PC access patterns online, improves IPC, and reduces LLC miss rate — while remaining small enough to be realistically implemented in hardware (ASIC/MAC units).

---

## 2. Methodology

```
Offline Training (Python)           Online Inference (C++ / ChampSim)
─────────────────────────           ──────────────────────────────────
Memory Traces                       prefetcher_operate()
     │                                    │
     ▼                                    ▼
Feature Extraction            State  ──► Inference Engine (pure C++)
 • PC hash                    (PC hash,   (matrix multiply + ReLU)
 • Address Delta Δt           Δt window)       │
 • Sliding window N=8              │            ▼
     │                        Action  ──► Issue Prefetch Request
     ▼                        (predicted Δ offset)
DQN / MLP Training
 • Reward: +10 hit, -5 pollution, -2 BW overload
     │
     ▼
Export weights.h (constexpr C++ arrays)
```

**Key design constraints** (hardware co-design):
- **Why DQN / MLP?** Hardware latency constraints (< 10 cycles) and strict area/power budgets preclude complex sequence models like RNNs or Transformers. A shallow MLP (≤ 3 hidden layers, ≤ 128 neurons per layer) using purely Matrix Multiplication + ReLU maps perfectly to pipelined ASIC MAC units.
- **State/Action/Reward Design:**
  - *State:* History window of size $N$, containing `(PC_Hash, Address_Delta)`. Delta is used over absolute addresses to ensure generalizability.
  - *Action:* Discrete offset predictions (e.g., $0, \pm1, \pm2$ cache lines). Action $0$ represents "do not prefetch".
  - *Reward:* Strongly penalizes cache pollution (-5) and bandwidth overuse (-2), while rewarding hits (+10). This teaches the agent to abstain from guessing on irregular pointer-chasing patterns.
- Inference in pure C++ with **zero dynamic memory allocation** — no `new`, no `std::vector`
- Weights stored as `constexpr std::array` — equivalent to SRAM-baked weights in silicon

### Future Architecture: Handling Workload Heterogeneity
To address the variance between different game engines (e.g., sparse asset streaming vs. dense rendering) without exceeding ASIC budgets, the project architecture plans to support:
- **Mixture of Experts (MoE) / Gating:** Deploying multiple tiny MLPs specialized in different patterns (e.g., Streaming vs. Pointer-chasing). A lightweight hardware performance counter routes inference to the best-performing expert dynamically.
- **Loadable Per-Game Profiles:** Treating the `constexpr` weights as SRAM regions that can be rewritten by OS/Firmware updates or loaded specifically per-game, acting like a "GPU driver update" for the prefetcher.

---

## 3. Experiments

### Architecture Under Test
A next-gen game console profile (PlayStation 5 / Xbox Series X class):

| Component | Specification |
|-----------|--------------|
| CPU | 3.5 GHz, Out-of-Order, ROB=352 |
| L1D Cache | 32 KB, 8-way, 4-cycle latency |
| L2 Cache | 512 KB, 8-way, 9-cycle latency |
| LLC | 4 MB, 16-way, 30-cycle latency |
| DRAM | 14 GT/s × 4 channels (≈ GDDR6) |

### Simulation Setup
- **Simulator:** [ChampSim](https://github.com/ChampSim/ChampSim) (trace-driven)
- **Warmup:** 10M instructions
- **Evaluation:** 50M instructions
- **Traces:** Synthetic game workload (40% streaming / 30% stride-2 / 30% irregular), extended with real SPEC CPU / DPC3 traces

### Metrics
| Metric | Description |
|--------|-------------|
| **IPC** | Instructions Per Cycle — higher is better |
| **LLC MPKI** | LLC Load Misses Per Kilo Instructions — lower is better |
| **DRAM BW** | DRAM bandwidth utilization (GB/s) — lower means less waste |

---

## 4. Optimization Comparison

### Baseline Results (Synthetic Game Trace)

| Configuration | IPC | LLC MPKI | DRAM BW |
|---------------|-----|----------|---------|
| No Prefetcher | 0.2440 | — | — |
| ip_stride + next_line | 0.2648 | — | — |
| **RL Prefetcher** *(in progress)* | TBD | TBD | TBD |

> ip_stride + next_line achieves **+8.6% IPC** over no-prefetch on the synthetic trace.
> The RL prefetcher targets **>+15% IPC** with lower LLC MPKI on irregular access patterns.

### Expected Trade-offs

| Aspect | Traditional Prefetcher | RL Prefetcher |
|--------|----------------------|---------------|
| Irregular pattern accuracy | Low | High |
| Cache pollution on random access | High | Low (reward penalizes it) |
| Hardware area (SRAM) | ~KB (stride table) | ~2–4 KB (weights + feature buffer) |
| Inference latency | 1 cycle (lookup) | ~5–10 cycles (matrix multiply, pipelined) |
| Adaptability to new workloads | None | Online fine-tuning possible |

---

## Project Structure

```
smart-memory-prefetcher/
├── ChampSim/                     # Simulator (submodule-style clone)
├── champsim_patches/             # Our config files and Makefile patches
│   ├── game_console_config.json  # ip_stride + next_line baseline config
│   └── game_console_no_prefetch.json
├── scripts/
│   ├── run_baseline.sh           # Batch simulation runner
│   ├── parse_results.py          # Log → CSV parser
│   ├── generate_synthetic_trace.py
│   ├── extract_features.py       # [Task 2] Trace → training data
│   ├── train_rl_model.py         # [Task 3] DQN training
│   └── export_weights.py         # [Task 4] .pth → weights.h
├── ChampSim/prefetcher/
│   └── rl_prefetcher/
│       ├── rl_prefetcher.cc      # [Task 5] ChampSim integration
│       ├── inference_engine.hpp  # [Task 4] Zero-dependency C++ inference
│       └── weights.h             # [Task 4] Exported model weights
├── traces/                       # Trace files (not committed, large)
├── weights/                      # Trained model weights
├── results/                      # Simulation output logs
├── baseline_results.csv
└── phase1_history.md
```

---

## Build & Run

```bash
# 1. Build ChampSim binaries
cd ChampSim
cp ../champsim_patches/game_console_no_prefetch.json .
cp ../champsim_patches/game_console_config.json .
python3 config.sh game_console_no_prefetch.json && make -j4
python3 config.sh game_console_config.json     && make -j4
cd ..

# 2. Generate synthetic test trace
python3 scripts/generate_synthetic_trace.py --instructions 5000000

# 3. Run simulations
./scripts/run_baseline.sh 10 50   # 10M warmup, 50M sim

# 4. Parse results
python3 scripts/parse_results.py
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Simulator | ChampSim (C++17) |
| ML Training | Python 3.10+, PyTorch |
| C++ Inference | Pure C++17, zero external dependencies |
| Hardware Target | ASIC (TSMC N4-class process assumed) |
