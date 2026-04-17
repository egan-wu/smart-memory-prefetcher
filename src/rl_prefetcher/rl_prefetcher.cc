#include "rl_prefetcher.h"
#include "inference_engine.hpp"
#include <iostream>

namespace {
    rl_prefetcher_namespace::InferenceEngine engine;
    constexpr size_t WINDOW_SIZE = 8;
    uint64_t pc_hash(uint64_t ip) { return (ip ^ (ip >> 2) ^ (ip >> 5)) & 0x3FF; }
}

void rl_prefetcher::prefetcher_initialize() { std::cout << "RL Prefetcher: Initialized" << std::endl; }

uint32_t rl_prefetcher::prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type, uint32_t metadata_in) {
    if (type != access_type::LOAD) return metadata_in;

    champsim::block_number block_addr{addr};
    uint64_t block_addr_val = block_addr.to<uint64_t>();
    uint64_t h_pc = pc_hash(ip.to<uint64_t>());
    auto& history = history_per_pc[h_pc];

    if (!history.empty() && history.back() == block_addr_val) return metadata_in;

    // Push the current access first, so inference predicts the FUTURE access
    history.push_back(block_addr_val);

    if (history.size() == WINDOW_SIZE + 1) {
        rl_prefetcher_namespace::InferenceEngine::InputArray input_features = {};
        input_features[0] = static_cast<float>(h_pc) / 1024.0f;
        for (size_t i = 1; i <= WINDOW_SIZE; ++i) {
            int64_t delta = static_cast<int64_t>(history[i]) - static_cast<int64_t>(history[i-1]);
            if (delta > 127) delta = 127;
            if (delta < -128) delta = -128;
            input_features[i] = static_cast<float>(delta) / 128.0f;
        }

        int action = engine.get_best_action(input_features);
        int delta_pred = engine.action_to_delta(action);

        if (delta_pred != 0) {
            // Shift back by block bits to convert block offset to byte address
            champsim::address pf_addr = champsim::address{(block_addr_val + delta_pred) << LOG2_BLOCK_SIZE};
            prefetch_line(pf_addr, true, metadata_in);
        }
        // Pop the oldest access
        history.pop_front();
    }

    return metadata_in;
}

uint32_t rl_prefetcher::prefetcher_cache_fill(champsim::address addr, long set, long way, uint8_t prefetch, champsim::address evicted_addr, uint32_t metadata_in) { return metadata_in; }
void rl_prefetcher::prefetcher_cycle_operate() {}
void rl_prefetcher::prefetcher_final_stats() {}
