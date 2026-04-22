#!/bin/bash
set -e

# Directory for storing traces
mkdir -p traces
cd traces

echo "Downloading standard SPEC CPU 2017 traces from public ChampSim repository..."

# mcf: Highly irregular pointer chasing (Graph traversal, caching nightmare)
if [ ! -f "mcf_605B.trace.xz" ]; then
    echo "Downloading mcf (Irregular Memory Access)..."
    curl -O https://champsimtraces.s3.us-east-2.amazonaws.com/spec2017/mcf_605B.trace.xz
else
    echo "mcf_605B.trace.xz already exists."
fi

# lbm: Highly regular streaming (Fluid dynamics, predictable stride)
if [ ! -f "lbm_700B.trace.xz" ]; then
    echo "Downloading lbm (Regular Streaming Access)..."
    curl -O https://champsimtraces.s3.us-east-2.amazonaws.com/spec2017/lbm_700B.trace.xz
else
    echo "lbm_700B.trace.xz already exists."
fi

echo "Download complete! These traces can now be used to run real-world evaluations."
echo "Example:"
echo "./scripts/run_eval.sh"
