#!/usr/bin/env bash
# run_baseline.sh - Batch run ChampSim for all traces under ./traces/
# Usage: ./scripts/run_baseline.sh [warmup_instr] [sim_instr]
#
# Runs both the no-prefetch and ip_stride+next_line configurations and saves
# output logs to ./results/. Designed for game-console architecture evaluation.

set -euo pipefail

CHAMPSIM_DIR="$(dirname "$0")/../ChampSim"
TRACES_DIR="$(dirname "$0")/../traces"
RESULTS_DIR="$(dirname "$0")/../results"

WARMUP=${1:-10}    # million instructions to warm up
SIM=${2:-50}       # million instructions to simulate

mkdir -p "${RESULTS_DIR}/no_pref"
mkdir -p "${RESULTS_DIR}/ipstride"

BINARY_NO_PREF="${CHAMPSIM_DIR}/bin/champsim_console_no_pref"
BINARY_IPSTRIDE="${CHAMPSIM_DIR}/bin/champsim_console_ipstride"

if [[ ! -x "${BINARY_NO_PREF}" || ! -x "${BINARY_IPSTRIDE}" ]]; then
    echo "[ERROR] Binaries not found. Run: cd ChampSim && python3 config.sh <config> && make" >&2
    exit 1
fi

shopt -s nullglob
TRACES=("${TRACES_DIR}"/*.xz "${TRACES_DIR}"/*.gz "${TRACES_DIR}"/*.champsimtrace)
shopt -u nullglob

if [[ ${#TRACES[@]} -eq 0 ]]; then
    echo "[WARN] No trace files found in ${TRACES_DIR}. Please add .xz/.gz trace files."
    echo "       Example: download from https://dpc3.compas.cs.stonybrook.edu/champsim-traces/"
    exit 0
fi

echo "Found ${#TRACES[@]} trace(s). Warmup=${WARMUP}M, Sim=${SIM}M instructions."
echo "---"

for TRACE in "${TRACES[@]}"; do
    BASENAME=$(basename "${TRACE}")
    STEM="${BASENAME%%.*}"

    echo "[RUN] no_pref    | ${BASENAME}"
    "${BINARY_NO_PREF}" \
        --warmup-instructions "${WARMUP}000000" \
        --simulation-instructions "${SIM}000000" \
        "${TRACE}" \
        > "${RESULTS_DIR}/no_pref/${STEM}.txt" 2>&1

    echo "[RUN] ipstride   | ${BASENAME}"
    "${BINARY_IPSTRIDE}" \
        --warmup-instructions "${WARMUP}000000" \
        --simulation-instructions "${SIM}000000" \
        "${TRACE}" \
        > "${RESULTS_DIR}/ipstride/${STEM}.txt" 2>&1
done

echo "---"
echo "Done. Logs saved to ${RESULTS_DIR}/"
echo "Run: python3 scripts/parse_results.py to generate baseline_results.csv"
