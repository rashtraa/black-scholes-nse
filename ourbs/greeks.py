"""Greeks of our model, derived by differentiating the Black-Scholes formula.

Units: delta and gamma per Rs 1 move in the share, theta per calendar day,
vega per 1 percentage point of volatility, rho per 1 percentage point of r.
"""
import numpy as np

from .model import d1_d2
from .normal import cdf, pdf


def greeks(S, K, T, r, sigma, kind="call", D=0.0):
    S_adj = np.asarray(S, dtype=float) - D
    d1, d2 = d1_d2(S_adj, K, T, r, sigma)
    root_t = np.sqrt(T)
    disc_K = K * np.exp(-r * np.asarray(T))
    bell = pdf(d1)

    gamma = bell / (S_adj * sigma * root_t)
    vega = S_adj * bell * root_t
    decay = -S_adj * bell * sigma / (2 * root_t)
    if kind == "call":
        delta, theta, rho = cdf(d1), decay - r * disc_K * cdf(d2), T * disc_K * cdf(d2)
    elif kind == "put":
        delta, theta, rho = cdf(d1) - 1, decay + r * disc_K * cdf(-d2), -T * disc_K * cdf(-d2)
    else:
        raise ValueError("kind must be 'call' or 'put'")
    return {"delta": delta, "gamma": gamma, "theta": theta / 365, "vega": vega / 100, "rho": rho / 100}
