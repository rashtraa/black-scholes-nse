"""The standard normal distribution, written from scratch.

Black-Scholes needs N(x), the area under the bell curve to the left of x.
There is no closed form for that area, so we use the polynomial
approximation from Abramowitz & Stegun (26.2.17), the one Hull prints.
It is accurate to about 7.5e-8, far finer than any option price quote.
We check it against direct numerical integration (Simpson's rule) in the tests.
"""
import numpy as np

SQRT_2PI = np.sqrt(2 * np.pi)
_GAMMA = 0.2316419
_A = (0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429)


def _scalar_or_array(x):
    return float(x) if np.ndim(x) == 0 else x


def pdf(x):
    """Height of the bell curve: N'(x) = e^(-x^2/2) / sqrt(2 pi)."""
    x = np.asarray(x, dtype=float)
    return _scalar_or_array(np.exp(-x * x / 2) / SQRT_2PI)


def cdf(x):
    """N(x) = P(Z <= x) for a standard normal Z."""
    x = np.asarray(x, dtype=float)
    ax = np.abs(x)
    k = 1.0 / (1.0 + _GAMMA * ax)
    poly = k * (_A[0] + k * (_A[1] + k * (_A[2] + k * (_A[3] + k * _A[4]))))
    upper = 1.0 - np.exp(-ax * ax / 2) / SQRT_2PI * poly
    return _scalar_or_array(np.where(x >= 0, upper, 1.0 - upper))


def cdf_by_integration(x, n=2000):
    """N(x) by integrating the bell curve with Simpson's rule (used to test cdf)."""
    h = x / n
    grid = np.linspace(0.0, x, n + 1)
    weights = np.ones(n + 1)
    weights[1:-1:2], weights[2:-1:2] = 4, 2
    return 0.5 + h / 3 * np.sum(weights * pdf(grid))


def inverse_cdf(p, lo=-10.0, hi=10.0, iterations=80):
    """The x with N(x) = p, found by bisection (N is increasing)."""
    p = np.asarray(p, dtype=float)
    lo, hi = np.full(p.shape, lo), np.full(p.shape, hi)
    for _ in range(iterations):
        mid = (lo + hi) / 2
        below = cdf(mid) < p
        lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
    return _scalar_or_array((lo + hi) / 2)


def standard_normal_draws(n, seed=None):
    """n independent N(0,1) numbers via the Box-Muller transform.

    Two uniform numbers u1, u2 on (0,1) give two independent normals:
        z1 = sqrt(-2 ln u1) cos(2 pi u2),  z2 = sqrt(-2 ln u1) sin(2 pi u2)
    """
    rng = np.random.default_rng(seed)
    m = (n + 1) // 2
    u1 = 1.0 - rng.random(m)          # in (0, 1], avoids log(0)
    u2 = rng.random(m)
    radius = np.sqrt(-2.0 * np.log(u1))
    z = np.concatenate([radius * np.cos(2 * np.pi * u2), radius * np.sin(2 * np.pi * u2)])
    return z[:n]
