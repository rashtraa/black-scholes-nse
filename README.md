# Black-Scholes from Scratch, Tested on NSE Options

A Black-Scholes option-pricing engine built from first principles in Python,
down to its own normal distribution, then put up against real market
prices for **Reliance Industries** options on the National Stock Exchange of India.

**Question:** if we price options using only what the stock's own history
tells us, how close do we get to what the market charges? And where we
miss, why?

## Findings (RELIANCE, 16 Oct 2026, 23 Nov 2026 expiry)

| | |
|---|---|
| **The engine is correct** | The closed-form price, an 800-step binomial tree and a 500,000-path Monte Carlo agree to within ₹0.01 (ATM call ≈ ₹36.36). Put-call parity holds exactly. |
| **The market charges more volatility than history shows** | Historical volatility (63 days) is **20.6%**; at-the-money implied volatility is **24.8%**. With historical σ, the model underprices ATM options by about 15-19%. |
| **One σ doesn't fit all strikes** | Implied volatility rises from ~25% at the money to 32-34% at the wings: a volatility smile that constant-σ Black-Scholes cannot produce. |
| **Returns are fat-tailed** | Daily log returns have excess kurtosis of +3.1. Moves beyond 3σ happen on 0.95% of days, vs 0.27% under normality. |
| **The market obeys put-call parity** | The average deviation across 27 strikes is ₹1.52, or 0.13% of spot. |
| **Delta hedging works on real prices** | Over 31 monthly periods, hedging a short ATM call cut the P&L standard deviation from **4.3% to 0.8%** of the share price. The worst month improved from -16.9% to -1.7%. |
| **What's left is volatility mis-forecast** | Hedged P&L correlates **+0.83** with σ_charged² - σ_realised², as Black-Scholes theory predicts. |

![Implied volatility by strike](output/RELIANCE/fig5_implied_volatility.png)

![Model vs market premiums](output/RELIANCE/fig4_model_vs_market.png)

![Delta-hedging backtest](output/RELIANCE/fig7_hedging_backtest.png)

More charts are in [`output/RELIANCE/`](output/RELIANCE), with all numbers in
[`results.md`](output/RELIANCE/results.md) and the per-strike table in
[`chain.csv`](output/RELIANCE/chain.csv).

## What's built

Everything in `ourbs/` is written from scratch. numpy is used for array
arithmetic and matplotlib for charts; no finance or statistics libraries.

| Module | What it does |
|---|---|
| `normal.py` | N(x) via the Abramowitz-Stegun polynomial (error < 7.5e-8), verified against our own Simpson's-rule integration; inverse N by bisection; Box-Muller normal random numbers |
| `model.py` | Black-Scholes-Merton call and put, cash dividends (S0 - D), risk-neutral exercise probability N(d2), no-arbitrage bounds |
| `greeks.py` | Delta, gamma, theta, vega and rho, derived analytically |
| `implied_vol.py` | Implied volatility: Newton's method on vega, with bisection fallback |
| `binomial.py` | Cox-Ross-Rubinstein tree (European and American): an independent check on the formula |
| `simulation.py` | Risk-neutral Monte Carlo of ln S_T: a third independent check |
| `volatility.py` | Log returns, historical and rolling volatility, return moments, bonus/split adjustment |
| `hedging.py` | Delta-hedging backtest on real daily closes |
| `nse_data.py` | Readers for NSE price history, F&O bhavcopy (old and UDiFF formats) and option-chain CSVs |

`analysis.py` runs the whole study and writes `results.md`, `results.json`,
`chain.csv` and 7 figures to `output/<SYMBOL>/`. The theory behind each
step is in [`docs/theory.md`](docs/theory.md).

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q        # engine tests
python analysis.py         # runs on bundled demo data until real data is added
```

To reproduce the Reliance results, or run any other NSE stock:

1. Download the data from NSE as described in [`data/README.md`](data/README.md):
   three years of daily prices into `data/stock/`, and one F&O bhavcopy into
   `data/options/`. NSE data is not redistributed in this repo.
2. Edit [`config.py`](config.py): symbol, lot size, risk-free rate (91-day
   T-bill), dividends, bonus/split dates, and the expiry to study.
3. Run `python analysis.py`.

Without real data, the pipeline runs on generated files for a fictional
share called `DEMO` (`data/demo/`), clearly labelled as fake in its output.

## Method notes

- **σ for pricing:** 63-trading-day historical volatility up to the trade
  date, so only information available that day is used.
- **Risk-free rate:** the 91-day T-bill yield (5.7281%), converted to continuous
  compounding (5.6876%) to match the model's e^(-rT).
- **Corporate actions:** Reliance's 1:1 bonus (ex-date 28 Oct 2024) halves
  the raw price overnight. Earlier prices are divided by 2, so the bonus
  isn't mistaken for a -50% crash. The code also flags any other one-day
  move over 15%.
- **Liquidity:** strikes with zero volume are dropped, since their closing
  prices are stale. Implied volatility is shown for out-of-the-money options
  only, because deep in-the-money premiums are mostly intrinsic value.
- **Expiry:** the November contract (38 days). The October contract had 11
  days left, too little time value for a meaningful comparison.

## Limitations

- Constant σ and lognormal returns are exactly the assumptions the data
  rejects (Figures 1, 2 and 5). The project measures these failures but
  doesn't model them; that would be the next step, e.g. stochastic or local
  volatility.
- The backtest hedges once a day and ignores brokerage, STT and bid-ask
  spreads.
- Option and stock closing prices are not perfectly synchronous.
- The model-vs-market comparison uses one stock on one date.

## Background

Built as a project around the Financial Derivatives syllabus at the Madras
School of Economics. It covers options and no-arbitrage bounds, put-call
parity, binomial trees, Brownian motion and Itô's lemma, Black-Scholes-Merton,
the Greeks, delta hedging and implied volatility.
