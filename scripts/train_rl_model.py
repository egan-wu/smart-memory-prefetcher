#!/usr/bin/env python3
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

class HardwarePrefetcherMLP(nn.Module):
    def __init__(self, input_dim=9, num_actions=9):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, num_actions)
        )
    def forward(self, x):
        return self.network(x)

def cache_pollution_loss(predictions, targets):
    ce_loss = nn.CrossEntropyLoss(reduction='none')(predictions, targets)
    probs = torch.softmax(predictions, dim=1)
    wrong_actions_mask = torch.ones_like(probs)
    wrong_actions_mask.scatter_(1, targets.unsqueeze(1), 0.0)
    wrong_actions_mask[:, 0] = 0.0
    pollution_prob = (probs * wrong_actions_mask).sum(dim=1)
    weights = 1.0 + (pollution_prob * 5.0)
    return (ce_loss * weights).mean()

def train():
    data = np.load("training_data.npz")
    X = data['X'].astype(np.float32)
    y = data['y'].astype(np.int64)
    X[:, 0] = X[:, 0] / 1024.0
    X[:, 1:] = X[:, 1:] / 128.0
    X_t, y_t = torch.tensor(X), torch.tensor(y)
    loader = DataLoader(TensorDataset(X_t, y_t), batch_size=2048, shuffle=True)
    model = HardwarePrefetcherMLP()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    for epoch in range(3):
        for bx, by in loader:
            optimizer.zero_grad()
            loss = cache_pollution_loss(model(bx), by)
            loss.backward()
            optimizer.step()
    torch.save(model.state_dict(), "weights/model_weights.pth")

if __name__ == "__main__":
    train()
