# Phase 1 Development History
## Task 1 — ChampSim Environment Setup & Baseline Establishment

**Date:** 2026-04-08
**Branch:** main

---

### Objective

Set up the ChampSim simulation environment and establish performance baselines using traditional hardware prefetchers. The target architecture is modeled after next-gen game consoles (PlayStation 5 / Xbox Series X class), featuring high-bandwidth GDDR6-style memory and a tuned cache hierarchy.

---

### Changes Made

#### 1. ChampSim Repository
- Cloned the official [ChampSim](https://github.com/ChampSim/ChampSim) repository into `ChampSim/`.
- Initialized the `vcpkg` submodule; however, `bzip2` failed to build on `arm64-osx` via vcpkg.
- **Resolution:** Switched to Homebrew for all C++ dependencies (`fmt`, `nlohmann-json`, `cli11`, `bzip2`, `xz`, `zlib`, `catch2`).

#### 2. `ChampSim/Makefile` (modified)
- Replaced the `vcpkg`-based `CPPFLAGS` / `LDFLAGS` / `LDLIBS` block with Homebrew paths under `/opt/homebrew/opt/`.
- Removed the `-lCLI11` linker flag — CLI11 is a header-only library and does not produce a `.a`/`.dylib`.

#### 3. `ChampSim/absolute.options` (modified)
- Removed the dangling `-isystem ` token (no argument) that was left at the end of the file by the `config.sh` code generator.
- This caused `module_decl.inc` to be invisible to the compiler because the malformed flag consumed the OBJ_ROOT `-I` path that follows it.

#### 4. `ChampSim/game_console_config.json` (new)
- Game-console-tuned architecture config for the `champsim_console_ipstride` binary.
- Key specs vs. the stock `champsim_config.json`:

| Parameter | Stock | Game Console |
|-----------|-------|--------------|
| CPU Frequency | 4000 MHz | 3500 MHz |
| L1D size | 64 sets × 12 ways (48 KB) | 64 sets × 8 ways (32 KB) |
| L2C prefetcher | none | `ip_stride` |
| LLC size | 2048 sets × 16 ways (2 MB) | 4096 sets × 16 ways (4 MB) |
| LLC prefetcher | none | `next_line` |
| LLC latency | 20 cycles | 30 cycles |
| DRAM data rate | 3200 MT/s × 1 ch | 14000 MT/s × 4 ch (≈ GDDR6) |
| DRAM tCAS/tRCD/tRP | 24 | 14 (lower latency GDDR6) |

#### 5. `ChampSim/game_console_no_prefetch.json` (new)
- Identical architecture as above but with **all prefetchers disabled** (`"prefetcher": "no"`).
- Serves as the pure baseline (lower bound) for IPC/MPKI comparisons.

#### 6. `scripts/run_baseline.sh` (new)
- Bash script that iterates over all `.xz` / `.gz` / `.champsimtrace` files under `traces/`.
- Runs both `champsim_console_no_pref` and `champsim_console_ipstride` for each trace.
- Configurable warmup and simulation instruction counts (default: 10M warmup / 50M sim).
- Saves output logs to `results/no_pref/` and `results/ipstride/`.

#### 7. `scripts/parse_results.py` (new)
- Python parser that scans all `results/<config>/*.txt` log files.
- Extracts: **IPC**, **LLC MPKI** (load misses per kilo instructions), **DRAM bandwidth (GB/s)**.
- Outputs `baseline_results.csv` and prints a formatted summary table to stdout.

#### 8. `scripts/generate_synthetic_trace.py` (new)
- Generates a synthetic ChampSim binary trace (48-byte record format, gzip-compressed).
- Mixed access pattern to stress-test different prefetcher strategies:
  - 40% sequential streaming → friendly to `next_line`
  - 30% stride-2 pattern → friendly to `ip_stride`
  - 30% irregular/random (pointer-chasing) → represents game scene graph / asset streaming
- Used for end-to-end pipeline validation before real traces are available.

---

### Build Artifacts

| Binary | Config | Prefetcher |
|--------|--------|------------|
| `ChampSim/bin/champsim_console_no_pref` | `game_console_no_prefetch.json` | None |
| `ChampSim/bin/champsim_console_ipstride` | `game_console_config.json` | L2C: ip_stride, LLC: next_line |

---

### Baseline Results (synthetic trace, 1M sim instructions)

| Config | IPC | Notes |
|--------|-----|-------|
| `no_pref` | 0.2440 | Lower bound |
| `ipstride` | 0.2648 | +8.6% over no_pref |

> **Target for RL prefetcher (Task 3–5):** Exceed `ipstride` IPC while reducing LLC MPKI and DRAM bandwidth usage on irregular access patterns.

---

### Known Issues / Limitations

1. **MPKI and DRAM BW not captured yet** — `parse_results.py` regex patterns need tuning against ChampSim's exact output format; currently parses IPC correctly but MPKI/BW return `N/A`.
2. **Synthetic trace only** — Real game/graphics traces (SPEC CPU, DPC3 traces) should replace or supplement the synthetic trace before final evaluation.
3. **Binaries not committed** — `ChampSim/bin/` is excluded from git (large compiled objects). Re-build with `python3 config.sh <config>.json && make`.

---

### Rebuild Instructions

```bash
# No-prefetch baseline
cd ChampSim
python3 config.sh game_console_no_prefetch.json && make -j4

# ip_stride + next_line baseline
python3 config.sh game_console_config.json && make -j4

# Run simulations (add traces to ./traces/ first)
cd ..
./scripts/run_baseline.sh 10 50       # 10M warmup, 50M sim

# Parse results
python3 scripts/parse_results.py
```
