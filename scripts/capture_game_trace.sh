#!/bin/bash
set -e

# Default settings
MAX_INSTRUCTIONS=10000000

if [ "$#" -lt 2 ]; then
    echo "=========================================================="
    echo "Automated Open-Source Game Trace Capturing Script"
    echo "=========================================================="
    echo "Usage: ./scripts/capture_game_trace.sh <output_trace_name> <command_to_run>"
    echo ""
    echo "Example:"
    echo "  ./scripts/capture_game_trace.sh my_godot_demo ./godot_demo.x86_64 --headless"
    echo ""
    echo "This script runs the provided executable under Valgrind,"
    echo "intercepts the memory access logs, and streams them directly"
    echo "into the python ChampSim converter without saving massive txt logs."
    echo "=========================================================="
    exit 1
fi

TRACE_NAME=$1
shift
# We use "$@" directly later to preserve argument quoting.
OUTPUT_FILE="traces/${TRACE_NAME}.champsimtrace.gz"

echo "[1/3] Checking dependencies..."
if ! command -v valgrind &> /dev/null; then
    echo "Error: valgrind is not installed. Please install it first (e.g., sudo apt-get install valgrind)."
    exit 1
fi

mkdir -p traces

echo "[2/3] Starting execution and trace capture for: $@"
echo "      Output will be streamed to: ${OUTPUT_FILE}"
echo "      (This may take a while depending on the complexity of the application...)"

# Run valgrind with the lackey tool, capture only memory traces.
# The 2>&1 redirects valgrind's stderr (where it prints traces) to stdout,
# so we can pipe it into our python script.
valgrind --tool=lackey --trace-mem=yes "$@" 2>&1 | \
python3 scripts/txt_to_champsim_trace.py --input - --out "$OUTPUT_FILE" --max_inst $MAX_INSTRUCTIONS

echo "[3/3] Trace successfully captured and compressed."
ls -lh "$OUTPUT_FILE"
