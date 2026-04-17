#ifndef RL_PREFETCHER_H
#define RL_PREFETCHER_H

#include "cache.h"
#include <map>
#include <deque>

struct rl_prefetcher : champsim::modules::prefetcher {
    std::map<uint64_t, std::deque<uint64_t>> history_per_pc;

    using prefetcher::prefetcher;
    void prefetcher_initialize();
    uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type, uint32_t metadata_in);
    uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way, uint8_t prefetch, champsim::address evicted_addr, uint32_t metadata_in);
    void prefetcher_cycle_operate();
    void prefetcher_final_stats();
};

#endif
