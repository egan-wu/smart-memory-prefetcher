#!/bin/bash
set -e
mkdir -p ChampSim/prefetcher/rl_prefetcher
cp src/rl_prefetcher/* ChampSim/prefetcher/rl_prefetcher/
cp champsim_patches/game_console_rl_prefetch.json ChampSim/
cd ChampSim
./config.sh game_console_rl_prefetch.json
make -j4
