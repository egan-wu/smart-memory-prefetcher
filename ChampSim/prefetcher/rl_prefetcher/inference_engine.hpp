#ifndef RL_PREFETCHER_INFERENCE_ENGINE_HPP
#define RL_PREFETCHER_INFERENCE_ENGINE_HPP

#include <array>
#include <algorithm>
#include "weights.h"

namespace rl_prefetcher {

class InferenceEngine {
public:
    // Input features: 9 (PC_Hash + 8 Deltas)
    // Hidden layers: 64 neurons each
    // Output actions: 9

    using InputArray = std::array<float, 9>;
    using OutputArray = std::array<float, 9>;

    // Performs a forward pass through the hardware-constrained MLP.
    // Zero dynamic memory allocation. Everything lives on the stack.
    OutputArray infer(const InputArray& input) const {
        std::array<float, 64> hidden1 = {};
        std::array<float, 64> hidden2 = {};
        OutputArray output = {};

        // --- Layer 1: Input (9) -> Hidden1 (64) ---
        // PyTorch stores weights as [out_features, in_features]
        // So memory layout is row-major: 64 rows of 9 elements.
        for (int i = 0; i < 64; ++i) {
            float sum = layer1_bias[i];
            for (int j = 0; j < 9; ++j) {
                sum += input[j] * layer1_weights[i * 9 + j];
            }
            // ReLU activation
            hidden1[i] = std::max(0.0f, sum);
        }

        // --- Layer 2: Hidden1 (64) -> Hidden2 (64) ---
        for (int i = 0; i < 64; ++i) {
            float sum = layer2_bias[i];
            for (int j = 0; j < 64; ++j) {
                sum += hidden1[j] * layer2_weights[i * 64 + j];
            }
            // ReLU activation
            hidden2[i] = std::max(0.0f, sum);
        }

        // --- Layer 3: Hidden2 (64) -> Output (9) ---
        for (int i = 0; i < 9; ++i) {
            float sum = layer3_bias[i];
            for (int j = 0; j < 64; ++j) {
                sum += hidden2[j] * layer3_weights[i * 64 + j];
            }
            // No activation on the final output (logits)
            output[i] = sum;
        }

        return output;
    }

    // Helper function to find the best action (argmax)
    int get_best_action(const InputArray& input) const {
        OutputArray logits = infer(input);

        int best_action = 0;
        float max_val = logits[0];

        for (int i = 1; i < 9; ++i) {
            if (logits[i] > max_val) {
                max_val = logits[i];
                best_action = i;
            }
        }

        return best_action;
    }

    // Maps the discrete action [0, 8] back to a cache line delta offset
    int action_to_delta(int action) const {
        // Based on Python labeling:
        // 0 -> 0 (No prefetch)
        // 1..4 -> +1, +2, +3, +4
        // 5..8 -> -1, -2, -3, -4
        if (action == 0) return 0;
        if (action >= 1 && action <= 4) return action;
        if (action >= 5 && action <= 8) return -(action - 4);
        return 0;
    }
};

} // namespace rl_prefetcher

#endif // RL_PREFETCHER_INFERENCE_ENGINE_HPP