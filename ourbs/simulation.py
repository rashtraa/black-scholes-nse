"""Monte Carlo: price an option by simulating the share in a risk-neutral world.

Ito's lemma on ln S gives  S_T = S0 exp((r - sigma^2/2) T + sigma sqrt(T) Z),
with Z standard normal (drawn with our own Box-Muller generator). Averaging
the discounted payoff over many draws estimates the option price, a third
independent check on the Black-Scholes formula.
"""
import numpy as np

from .normal import standard_normal_draws


def terminal_prices(S, T, growth, sigma, n, seed=None):
    z = standard_normal_draws(n, seed)
    return S * np.exp((growth - sigma**2 / 2) * T + sigma * np.sqrt(T) * z)


def mc_price(S, K, T, r, sigma, kind="call", n=200_000, D=0.0, seed=None):
    S_T = terminal_prices(S - D, T, r, sigma, n, seed)
    payoff = np.maximum(S_T - K, 0) if kind == "call" else np.maximum(K - S_T, 0)
    disc = np.exp(-r * T) * payoff
    est = disc.mean()
    se = disc.std(ddof=1) / np.sqrt(n)
    return {"price": est, "std_error": se, "ci_95": (est - 1.96 * se, est + 1.96 * se)}
