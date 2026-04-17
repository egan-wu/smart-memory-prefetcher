#ifndef RL_PREFETCHER_INFERENCE_ENGINE_HPP
#define RL_PREFETCHER_INFERENCE_ENGINE_HPP
#include <array>
#include <algorithm>
#include "weights.h"
namespace rl_prefetcher_namespace {
class InferenceEngine {
public:
    using InputArray = std::array<float, 9>;
    using OutputArray = std::array<float, 9>;
    OutputArray infer(const InputArray& input) const {
        std::array<float, 64> hidden1 = {};
        std::array<float, 64> hidden2 = {};
        OutputArray output = {};
        for (int i = 0; i < 64; ++i) {
            float sum = layer1_bias[i];
            for (int j = 0; j < 9; ++j) sum += input[j] * layer1_weights[i * 9 + j];
            hidden1[i] = std::max(0.0f, sum);
        }
        for (int i = 0; i < 64; ++i) {
            float sum = layer2_bias[i];
            for (int j = 0; j < 64; ++j) sum += hidden1[j] * layer2_weights[i * 64 + j];
            hidden2[i] = std::max(0.0f, sum);
        }
        for (int i = 0; i < 9; ++i) {
            float sum = layer3_bias[i];
            for (int j = 0; j < 64; ++j) sum += hidden2[j] * layer3_weights[i * 64 + j];
            output[i] = sum;
        }
        return output;
    }
    int get_best_action(const InputArray& input) const {
        OutputArray logits = infer(input);
        int best_action = 0; float max_val = logits[0];
        for (int i = 1; i < 9; ++i) {
            if (logits[i] > max_val) { max_val = logits[i]; best_action = i; }
        }
        return best_action;
    }
    int action_to_delta(int action) const {
        if (action == 0) return 0;
        if (action >= 1 && action <= 4) return action;
        if (action >= 5 && action <= 8) return -(action - 4);
        return 0;
    }
};
}
#endif
