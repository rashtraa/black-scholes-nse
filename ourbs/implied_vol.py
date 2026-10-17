"""Implied volatility: the sigma at which our model reproduces a market price.

The Black-Scholes price rises steadily with sigma, so there is exactly one
answer whenever the market price lies inside the no-arbitrage bounds. We use
Newton's method (fast: the slope is vega) and fall back to bisection (slow
but cannot fail) when Newton misbehaves, e.g. for deep in/out-of-the-money
options where vega is nearly zero.
"""
import numpy as np

from .greeks import greeks
from .model import no_arbitrage_bounds, price

SIGMA_MIN, SIGMA_MAX = 1e-4, 5.0


def implied_vol(market_price, S, K, T, r, kind, D=0.0, tol=1e-7):
    """Returns nan if the market price is outside the no-arbitrage bounds."""
    lo_bound, hi_bound = no_arbitrage_bounds(S, K, T, r, kind, D)
    if not lo_bound < market_price < hi_bound:
        return float("nan")
    f = lambda s: float(price(S, K, T, r, s, kind, D)) - market_price

    sigma = 0.3
    for _ in range(30):
        err = f(sigma)
        if abs(err) < tol:
            return sigma
        vega = float(greeks(S, K, T, r, sigma, kind, D)["vega"]) * 100
        if vega < 1e-6:
            break
        sigma -= err / vega
        if not SIGMA_MIN < sigma < SIGMA_MAX:
            break

    lo, hi = SIGMA_MIN, SIGMA_MAX
    if f(lo) > 0 or f(hi) < 0:
        return float("nan")
    while hi - lo > tol:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return (lo + hi) / 2
