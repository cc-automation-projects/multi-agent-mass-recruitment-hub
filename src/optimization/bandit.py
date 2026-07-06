"""
Thompson Sampling implementation for multi-armed bandit.
"""

import random


class ThompsonSampling:
    """
    Thompson Sampling for Bernoulli rewards.
    Each arm is represented by Beta(alpha, beta) distribution.
    """

    def __init__(self, n_arms: int, alpha_prior: float = 1.0, beta_prior: float = 1.0):
        self.n_arms = n_arms
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior
        self.alpha = [alpha_prior] * n_arms
        self.beta = [beta_prior] * n_arms

    def select_arm(self) -> int:
        samples = [random.betavariate(self.alpha[i], self.beta[i]) for i in range(self.n_arms)]
        return samples.index(max(samples))

    def update(self, arm: int, reward: float):
        self.alpha[arm] += reward
        self.beta[arm] += 1 - reward

    def get_probabilities(self) -> list[float]:
        return [self.alpha[i] / (self.alpha[i] + self.beta[i]) for i in range(self.n_arms)]
