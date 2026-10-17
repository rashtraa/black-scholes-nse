"""Delta-hedging backtest on the stock's real price history.

The Black-Scholes argument says a seller who charges the model price and
holds delta shares ends with (almost) zero profit or loss. We test that on
actual prices: at the start of each period we sell a one-month at-the-money
call at our model price, using only the volatility known on that day
(trailing historical vol), then rebalance the hedge at each daily close
until expiry. The final P&L tells us how well the model's promise held up,
and how much a seller would have made or lost by not hedging.
"""
import numpy as np

from .greeks import greeks
from .model import call_price
from .volatility import TRADING_DAYS, annualised_vol, log_returns


def backtest_short_call(dates, closes, r, vol_window=63, life_days=21):
    closes = np.asarray(closes, dtype=float)
    rets = log_returns(closes)
    dt = 1 / TRADING_DAYS
    results = []
    for start in range(vol_window, len(closes) - life_days, life_days):
        sigma = annualised_vol(rets[start - vol_window:start])
        S0, K, T = closes[start], closes[start], life_days * dt
        premium = float(call_price(S0, K, T, r, sigma))

        delta = float(greeks(S0, K, T, r, sigma)["delta"])
        cash = premium - delta * S0
        for k in range(1, life_days):
            S = closes[start + k]
            cash = cash * np.exp(r * dt)
            new_delta = float(greeks(S, K, T - k * dt, r, sigma)["delta"])
            cash -= (new_delta - delta) * S
            delta = new_delta
        S_T = closes[start + life_days]
        cash = cash * np.exp(r * dt)
        payoff = max(S_T - K, 0.0)

        results.append({
            "start": dates[start], "S0": S0, "sigma_used": sigma,
            "realised_vol": annualised_vol(rets[start:start + life_days]),
            "premium": premium, "payoff": payoff,
            "hedged_pnl": cash + delta * S_T - payoff,
            "unhedged_pnl": premium * np.exp(r * T) - payoff,
        })
    return results
