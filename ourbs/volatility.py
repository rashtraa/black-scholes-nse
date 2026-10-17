"""Estimating sigma, the one model input we cannot read off a screen.

u_i = ln(S_i / S_{i-1}) are the daily log returns. Their standard deviation s
is the volatility per trading day; sigma = s * sqrt(252) per year.
"""
import numpy as np

TRADING_DAYS = 252


def adjust_for_corporate_actions(dates, closes, actions):
    """Make prices before a bonus/split comparable with prices after it.

    actions = [(ex_date, factor)]: a 1:1 bonus or a 1-for-2 split has factor 2,
    so every close before the ex-date is divided by 2. An action is applied
    only if the raw data really shows the drop (NSE's files can already be
    adjusted). Returns (adjusted closes, list of notes for the report).
    """
    closes = np.array(closes, dtype=float)
    notes = []
    for ex_date, factor in actions:
        i = next((k for k, d in enumerate(dates) if d >= ex_date), None)
        if i is None or i == 0:
            notes.append(f"{ex_date}: outside the price history, ignored")
            continue
        ratio = closes[i] / closes[i - 1]
        if abs(ratio * factor - 1) < 0.3:
            closes[:i] /= factor
            notes.append(f"{ex_date}: prices before this date divided by {factor:g} "
                         f"(raw overnight move {ratio - 1:+.1%})")
        else:
            notes.append(f"{ex_date}: no price drop of 1/{factor:g} found (move {ratio - 1:+.1%}), "
                         "data looks already adjusted; left unchanged")
    return closes, notes


def suspicious_jumps(dates, closes, threshold=0.15):
    """Days with |log return| above threshold: possible unadjusted corporate actions."""
    rets = log_returns(closes)
    return [(dates[k + 1], float(x)) for k, x in enumerate(rets) if abs(x) > threshold]


def log_returns(closes):
    closes = np.asarray(closes, dtype=float)
    return np.log(closes[1:] / closes[:-1])


def annualised_vol(returns):
    return float(np.std(returns, ddof=1) * np.sqrt(TRADING_DAYS))


def rolling_vol(returns, window):
    """Annualised vol over each trailing window (nan until the window is full)."""
    out = np.full(len(returns), np.nan)
    for t in range(window, len(returns) + 1):
        out[t - 1] = annualised_vol(returns[t - window:t])
    return out


def describe_returns(returns):
    """Moments of daily log returns. A normal distribution has skew 0 and excess kurtosis 0."""
    r = np.asarray(returns, dtype=float)
    m, s = r.mean(), r.std(ddof=1)
    z = (r - m) / s
    return {
        "days": len(r),
        "mean_daily": m,
        "sd_daily": s,
        "annual_vol": s * np.sqrt(TRADING_DAYS),
        "skewness": float(np.mean(z**3)),
        "excess_kurtosis": float(np.mean(z**4) - 3),
        "worst_day": float(r.min()),
        "best_day": float(r.max()),
        "share_beyond_3sd": float(np.mean(np.abs(z) > 3)),   # normal: 0.27%
    }
