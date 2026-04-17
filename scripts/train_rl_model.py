#!/usr/bin/env python3
"""
train_rl_model.py — Task 3: Lightweight RL Model Training

This script trains a shallow MLP to predict memory access deltas based on history.
It enforces hardware constraints: max 3 hidden layers, 128 neurons, ReLU only.
It also implements an asymmetric loss function to heavily penalize false predictions
(which cause cache pollution) while being lenient on Action 0 (no prefetch).
"""

import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from pathlib import Path
import time

# --- Hardware Constrained Model Definition ---
class HardwarePrefetcherMLP(nn.Module):
    def __init__(self, input_dim=9, num_actions=9):
        super(HardwarePrefetcherMLP, self).__init__()
        # Strict constraints: <= 3 hidden layers, <= 128 neurons, ReLU only
        # We use 2 hidden layers for extreme latency minimization (< 10 cycles in ASIC)
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, num_actions)
        )

    def forward(self, x):
        return self.network(x)

# --- Custom Asymmetric Loss (Reward Modeling) ---
def cache_pollution_loss(predictions, targets):
    """
    Simulates the RL reward structure via asymmetric CrossEntropy.
    Rewards: Hit (+10), No-op (0), Pollution (-5).
    Instead of using non-differentiable argmax, we penalize the continuous probability mass
    assigned to non-zero actions when the target is 0, to stabilize training.
    """
    # Standard Cross Entropy
    ce_loss = nn.CrossEntropyLoss(reduction='none')(predictions, targets)

    # Calculate probability distribution
    probs = torch.softmax(predictions, dim=1)

    # Calculate how much probability mass is given to wrong, non-zero actions.
    # This represents the continuous risk of cache pollution.
    # We create a mask of wrong actions
    wrong_actions_mask = torch.ones_like(probs)
    wrong_actions_mask.scatter_(1, targets.unsqueeze(1), 0.0)

    # Ignore Action 0 from the pollution penalty because Action 0 doesn't pollute
    wrong_actions_mask[:, 0] = 0.0

    # Total probability mass on polluting actions
    pollution_prob = (probs * wrong_actions_mask).sum(dim=1)

    # Apply a multiplier based on the probability of a polluting prediction
    # Base weight is 1.0. The more confident it is in a wrong, non-zero action, the higher the penalty.
    pollution_penalty = 5.0
    weights = 1.0 + (pollution_prob * pollution_penalty)

    return (ce_loss * weights).mean()


def train(data_path, epochs, batch_size, lr, save_path):
    print(f"Loading data from {data_path}...")
    data = np.load(data_path)
    X = data['X'].astype(np.float32)
    y = data['y'].astype(np.int64)

    # Normalize PC_Hash and Deltas to help the MLP train faster
    # PC_Hash is [0, 1023], Deltas are roughly [-128, 127]
    X[:, 0] = X[:, 0] / 1024.0      # Normalize PC
    X[:, 1:] = X[:, 1:] / 128.0     # Normalize Deltas

    # Split into Train (80%) and Validation (20%)
    split_idx = int(len(X) * 0.8)
    X_train, y_train = torch.tensor(X[:split_idx]), torch.tensor(y[:split_idx])
    X_val, y_val = torch.tensor(X[split_idx:]), torch.tensor(y[split_idx:])

    train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model = HardwarePrefetcherMLP().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)

    print("\nStarting Training...")
    print("=" * 60)

    best_val_acc = 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0
        start_time = time.time()

        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)

            optimizer.zero_grad()
            outputs = model(batch_X)

            loss = cache_pollution_loss(outputs, batch_y)
            loss.backward()
            optimizer.step()

            total_loss += loss.item() * batch_X.size(0)

        avg_train_loss = total_loss / len(X_train)

        # Validation
        model.eval()
        correct = 0
        safe_preds = 0 # Count of Action 0 predictions
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                outputs = model(batch_X)
                preds = torch.argmax(outputs, dim=1)
                correct += (preds == batch_y).sum().item()
                safe_preds += (preds == 0).sum().item()

        val_acc = correct / len(X_val)
        safe_ratio = safe_preds / len(X_val)
        epoch_time = time.time() - start_time

        print(f"Epoch {epoch:02d}/{epochs} | Time: {epoch_time:.1f}s | "
              f"Train Loss: {avg_train_loss:.4f} | Val Acc: {val_acc:.4f} | "
              f"Safe Action (0) Ratio: {safe_ratio:.2f}")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), save_path)

    print("=" * 60)
    print(f"Training Complete. Best Validation Accuracy: {best_val_acc:.4f}")
    print(f"Model weights saved to {save_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, default="training_data.npz")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=2048)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--save", type=str, default="weights/model_weights.pth")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: Data file {data_path} not found.")
        exit(1)

    Path(args.save).parent.mkdir(parents=True, exist_ok=True)

    train(args.data, args.epochs, args.batch_size, args.lr, args.save)