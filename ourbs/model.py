"""Our Black-Scholes-Merton pricing model.

Assumptions (course notes, Part II-cont.):
  * the share follows dS = mu S dt + sigma S dz, so ln S_T is normal;
  * sigma and r are constant over the option's life;
  * no transaction costs, continuous trading, no arbitrage;
  * European exercise (NSE stock options are European).

Because an option and the share are driven by the same randomness, a
portfolio of -1 option and +delta shares is riskless and must earn r.
That gives the Black-Scholes equation; with the payoff as boundary
condition its solution is

    c = S0 N(d1) - K e^(-rT) N(d2)
    p = K e^(-rT) N(-d2) - S0 N(-d1)
    d1 = [ln(S0/K) + (r + sigma^2/2) T] / (sigma sqrt T),   d2 = d1 - sigma sqrt T

Known cash dividends during the option's life: replace S0 by S0 - D,
where D is the present value of those dividends.
"""
import numpy as np

from .normal import cdf


def pv_dividends(dividends, r, T):
    """dividends = [(years_from_now, amount), ...]; only those before expiry count."""
    return sum(amount * np.exp(-r * t) for t, amount in dividends if 0 < t <= T)


def d1_d2(S, K, T, r, sigma):
    S, K, T, sigma = (np.asarray(v, dtype=float) for v in (S, K, T, sigma))
    vol_root_t = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / vol_root_t
    return d1, d1 - vol_root_t


def call_price(S, K, T, r, sigma, D=0.0):
    S_adj = np.asarray(S, dtype=float) - D
    d1, d2 = d1_d2(S_adj, K, T, r, sigma)
    return S_adj * cdf(d1) - K * np.exp(-r * np.asarray(T)) * cdf(d2)


def put_price(S, K, T, r, sigma, D=0.0):
    S_adj = np.asarray(S, dtype=float) - D
    d1, d2 = d1_d2(S_adj, K, T, r, sigma)
    return K * np.exp(-r * np.asarray(T)) * cdf(-d2) - S_adj * cdf(-d1)


def price(S, K, T, r, sigma, kind, D=0.0):
    if kind == "call":
        return call_price(S, K, T, r, sigma, D)
    if kind == "put":
        return put_price(S, K, T, r, sigma, D)
    raise ValueError("kind must be 'call' or 'put'")


def prob_exercise(S, K, T, r, sigma, kind="call", D=0.0):
    """Risk-neutral probability of finishing in the money: N(d2) for a call."""
    _, d2 = d1_d2(np.asarray(S, dtype=float) - D, K, T, r, sigma)
    return cdf(d2) if kind == "call" else cdf(-d2)


def no_arbitrage_bounds(S, K, T, r, kind, D=0.0):
    """European bounds: max(S - D - Ke^-rT, 0) <= c <= S - D;  max(Ke^-rT - S + D, 0) <= p <= Ke^-rT."""
    disc_K, S_adj = K * np.exp(-r * T), S - D
    if kind == "call":
        return max(S_adj - disc_K, 0.0), S_adj
    return max(disc_K - S_adj, 0.0), disc_K
