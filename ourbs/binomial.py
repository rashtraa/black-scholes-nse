"""Our Cox-Ross-Rubinstein binomial tree: an independent route to the same price.

u = e^(sigma sqrt dt), d = 1/u, risk-neutral p = (e^(r dt) - d) / (u - d).
Work backwards from the payoffs: f = e^(-r dt) [p f_u + (1-p) f_d].
As the number of steps grows, the tree price converges to Black-Scholes,
which is a strong check that the formula code is right.
"""
import numpy as np


def crr_price(S, K, T, r, sigma, kind="call", steps=500, american=False, D=0.0):
    dt = T / steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    p = (np.exp(r * dt) - d) / (u - d)
    disc = np.exp(-r * dt)
    sign = 1 if kind == "call" else -1

    j = np.arange(steps + 1)
    S_T = (S - D) * u ** (steps - j) * d**j
    values = np.maximum(sign * (S_T - K), 0)
    for i in range(steps - 1, -1, -1):
        values = disc * (p * values[:-1] + (1 - p) * values[1:])
        if american:
            j = np.arange(i + 1)
            values = np.maximum(values, sign * ((S - D) * u ** (i - j) * d**j - K))
    return float(values[0])
