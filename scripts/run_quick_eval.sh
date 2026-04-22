#!/bin/bash
WARMUP=100000
SIM=1000000

echo "Running Simulation on Synthetic Trace..."
./ChampSim/bin/champsim_console_no_pref -w $WARMUP -i $SIM traces/synthetic_game.champsimtrace.gz > results/no_pref/synthetic_game.txt
./ChampSim/bin/champsim_console_ipstride -w $WARMUP -i $SIM traces/synthetic_game.champsimtrace.gz > results/ipstride/synthetic_game.txt
./ChampSim/bin/champsim_console_rl_prefetch -w $WARMUP -i $SIM traces/synthetic_game.champsimtrace.gz > results/rl_prefetch/synthetic_game.txt

echo "Running Simulation on Minetest Trace..."
./ChampSim/bin/champsim_console_no_pref -w $WARMUP -i $SIM traces/minetest_trace.champsimtrace.gz > results/no_pref/minetest.txt
./ChampSim/bin/champsim_console_ipstride -w $WARMUP -i $SIM traces/minetest_trace.champsimtrace.gz > results/ipstride/minetest.txt
./ChampSim/bin/champsim_console_rl_prefetch -w $WARMUP -i $SIM traces/minetest_trace.champsimtrace.gz > results/rl_prefetch/minetest.txt
echo "Done!"
