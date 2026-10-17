"""Our Black-Scholes engine vs the NSE market: the full project pipeline.

    python analysis.py

Steps
  1. Study the share: returns, volatility, and whether ln S looks normal.
  2. Check our engine three ways (formula vs binomial tree vs Monte Carlo).
  3. Price the option chain with our model and compare to market premiums.
  4. Back out implied volatilities from the market with our solver.
  5. Test put-call parity on market prices.
  6. Greeks of the chain, per lot.
  7. Backtest: sell monthly ATM calls at our price and delta-hedge on real prices.
Writes figures, results.md and results.json to output/<SYMBOL or demo>/.
"""
import json
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import config
from ourbs import binomial, greeks as gk, hedging, implied_vol as iv, model, normal, simulation
from ourbs import volatility as vol
from ourbs.nse_data import load_options, load_stock_history

# ---------------------------------------------------------------- data ----
stock_dir, options_dir, symbol = config.STOCK_DIR, config.OPTIONS_DIR, config.SYMBOL
demo = not any(stock_dir.glob("*.csv")) and config.USE_DEMO_IF_EMPTY
if demo:
    stock_dir, options_dir, symbol = (config.ROOT / "data" / "demo" / "stock",
                                      config.ROOT / "data" / "demo" / "options", "DEMO")
OUT = config.ROOT / "output" / ("demo" if demo else symbol)
OUT.mkdir(parents=True, exist_ok=True)

dates, closes = load_stock_history(stock_dir)
closes, ca_notes = vol.adjust_for_corporate_actions(dates, closes, [] if demo else config.CORPORATE_ACTIONS)
jumps = vol.suspicious_jumps(dates, closes)
options = load_options(options_dir, symbol, config.OPTION_CHAIN)
r = config.RISK_FREE_RATE

# ---------------------------------------------------------------- style ---
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.dpi": 130, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "axes.edgecolor": INK_2, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 2, "legend.frameon": False,
    "axes.titleweight": "bold", "axes.titlesize": 11,
    "axes.prop_cycle": matplotlib.cycler(color=[BLUE, ORANGE, AQUA, YELLOW]),
})
md, results = [], {"symbol": symbol, "demo": demo, "risk_free_rate": r}


def save(fig, name, caption):
    fig.tight_layout()
    fig.savefig(OUT / name)
    plt.close(fig)
    md.append(f"\n![{caption}]({name})\n*{caption}*\n")


def table(header, rows):
    md.append("\n| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n")
    md.extend("| " + " | ".join(str(c) for c in row) + " |\n" for row in rows)


md.append(f"# Our Black-Scholes model vs the market: {symbol}\n")
if demo:
    md.append("\n> **DEMO RUN ON FAKE DATA.** No CSVs were found in data/stock, so this uses "
              "generated data for a made-up share called DEMO. These numbers say nothing about "
              "any real stock. See data/README.md for what to download.\n")

# ======================================================= 1. the share ====
rets = vol.log_returns(closes)
stats = vol.describe_returns(rets)
roll = {w: vol.rolling_vol(rets, w) for w in (21, 63, 252)}

trade_date = (None if demo else config.TRADE_DATE) or max(o["date"] for o in options)
idx = max(i for i, d in enumerate(dates) if d <= trade_date)
sigma_hist = vol.annualised_vol(rets[idx - config.VOL_WINDOW:idx])
results.update(trade_date=str(trade_date), sigma_hist=sigma_hist, return_stats=stats,
               history=f"{dates[0]} to {dates[-1]}")

md.append(f"\n## 1. The share\n\nPrice history {dates[0]} to {dates[-1]} ({len(closes)} trading days).\n")
for note in ca_notes:
    md.append(f"\n- Corporate action {note}.")
for d, x in jumps:
    md.append(f"\n- **Check:** {d} moved {x:+.1%} in one day. If that is a bonus, split or "
              "demerger, add it to CORPORATE_ACTIONS in config.py.")
md.append("\n")
table(["Statistic", "Value", "If ln S were exactly normal"], [
    ("Annualised volatility (whole sample)", f"{stats['annual_vol']:.2%}", ""),
    (f"Volatility used for pricing ({config.VOL_WINDOW} days to {trade_date})", f"{sigma_hist:.2%}", ""),
    ("Skewness of daily log returns", f"{stats['skewness']:+.3f}", "0"),
    ("Excess kurtosis", f"{stats['excess_kurtosis']:+.3f}", "0"),
    ("Days beyond 3 standard deviations", f"{stats['share_beyond_3sd']:.2%}", "0.27%"),
    ("Worst / best day", f"{stats['worst_day']:+.2%} / {stats['best_day']:+.2%}", ""),
])

fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
axes[0].plot(dates, closes, color=BLUE, lw=1.3)
axes[0].axvline(dates[idx], color=INK_2, ls="--", lw=1)
axes[0].set(title=f"{symbol}: closing price", ylabel="Rs")
for w, col in zip((21, 63, 252), (BLUE, ORANGE, AQUA)):
    axes[1].plot(dates[1:], roll[w], color=col, lw=1.3, label=f"{w}-day")
axes[1].set(title="Historical volatility (annualised), trailing windows", ylabel="sigma")
axes[1].legend(ncol=3)
save(fig, "fig1_share_and_volatility.png", "Volatility is not constant over time, although our model assumes it is")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
z = (rets - rets.mean()) / rets.std(ddof=1)
axes[0].hist(z, bins=70, density=True, color=BLUE, alpha=0.35, label="Standardised daily log returns")
xs = np.linspace(-6, 6, 400)
axes[0].plot(xs, normal.pdf(xs), color=ORANGE, label="Our normal density N'(x)")
axes[0].set(title="Are log returns normal?", xlim=(-6, 6), xlabel="Standard deviations from the mean")
axes[0].legend()
probs = (np.arange(1, len(z) + 1) - 0.5) / len(z)
axes[1].scatter(normal.inverse_cdf(probs), np.sort(z), s=8, color=BLUE, label="Observed")
axes[1].plot([-4, 4], [-4, 4], color=ORANGE, lw=1.5, label="Perfectly normal")
axes[1].set(title="Normal Q-Q plot", xlabel="Normal quantile (our inverse N)", ylabel="Observed quantile")
axes[1].legend()
save(fig, "fig2_normality_check.png", "Points bending away at the ends = fatter tails than the model assumes")

# ======================================================= option inputs ====
expiries = sorted({o["expiry"] for o in options if o["date"] == trade_date and o["expiry"] > trade_date})
expiry = (None if demo else config.EXPIRY) or expiries[0]
if expiry not in expiries:
    raise SystemExit(f"EXPIRY {expiry} is not in the option data for {trade_date}; "
                     f"available: {', '.join(map(str, expiries))}")
chain = [o for o in options if o["date"] == trade_date and o["expiry"] == expiry]
spot = next((o["underlying"] for o in chain if o["underlying"]), None) or closes[idx]
T = (expiry - trade_date).days / 365
divs = [((d - trade_date).days / 365, amt) for d, amt in config.DIVIDENDS]
D = model.pv_dividends(divs, r, T)
results.update(expiry=str(expiry), spot=spot, T_years=T, pv_dividends=D)
md.append(f"\n## 2. Inputs on {trade_date}\n\nSpot S0 = Rs {spot:,.2f}; expiry {expiry} "
          f"(T = {T*365:.0f} days = {T:.4f} years); r = {r:.2%} (assumption); "
          f"PV of dividends D = Rs {D:.2f}; sigma = {sigma_hist:.2%} ({config.VOL_WINDOW}-day historical).\n")

# ======================================================= 2. engine check ====
strikes_all = sorted({o["strike"] for o in chain})
K_atm = min(strikes_all, key=lambda k: abs(k - spot))
bs_c = float(model.call_price(spot, K_atm, T, r, sigma_hist, D))
bs_p = float(model.put_price(spot, K_atm, T, r, sigma_hist, D))
steps = [10, 25, 50, 100, 200, 400, 800]
tree = [binomial.crr_price(spot, K_atm, T, r, sigma_hist, "call", n, D=D) for n in steps]
paths = [1_000, 5_000, 20_000, 100_000, 500_000]
mc = [simulation.mc_price(spot, K_atm, T, r, sigma_hist, "call", n, D=D, seed=1) for n in paths]
parity_gap = bs_c - bs_p - (spot - D - K_atm * np.exp(-r * T))
results["engine_check"] = {"strike": K_atm, "formula_call": bs_c, "tree_800": tree[-1],
                           "mc_500k": mc[-1]["price"], "mc_se": mc[-1]["std_error"], "parity_gap": parity_gap}

md.append("\n## 3. Is our engine right? Three independent methods\n")
table(["Method (ATM call, K = %s)" % f"{K_atm:,.0f}", "Price", "Difference from formula"], [
    ("Our Black-Scholes formula", f"{bs_c:.4f}", "-"),
    ("Our binomial tree, 800 steps", f"{tree[-1]:.4f}", f"{tree[-1] - bs_c:+.4f}"),
    ("Our Monte Carlo, 500,000 paths", f"{mc[-1]['price']:.4f} +/- {1.96*mc[-1]['std_error']:.4f}", f"{mc[-1]['price'] - bs_c:+.4f}"),
    ("Put-call parity on our prices: c - p - (S0 - D - Ke^-rT)", f"{parity_gap:.2e}", "should be 0"),
])
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(steps, tree, color=BLUE, marker="o", ms=5, label="Our binomial tree")
axes[0].axhline(bs_c, color=ORANGE, ls="--", label="Our Black-Scholes formula")
axes[0].set(xscale="log", title="Tree converges to the formula", xlabel="Steps", ylabel="ATM call (Rs)")
axes[0].legend()
est = np.array([m["price"] for m in mc])
half = np.array([1.96 * m["std_error"] for m in mc])
axes[1].fill_between(paths, est - half, est + half, color=BLUE, alpha=0.15, lw=0, label="95% interval")
axes[1].plot(paths, est, color=BLUE, marker="o", ms=5, label="Our Monte Carlo")
axes[1].axhline(bs_c, color=ORANGE, ls="--", label="Our Black-Scholes formula")
axes[1].set(xscale="log", title="Simulation converges to the formula", xlabel="Simulated paths")
axes[1].legend()
save(fig, "fig3_engine_check.png", "Three routes, one answer")

# ======================================================= 3-4. chain ====
traded = [o for o in chain if (o["volume"] is None or o["volume"] >= config.MIN_VOLUME) and o["price"] > 0]
rows, chain_out = [], []
for o in sorted(traded, key=lambda o: (o["strike"], o["kind"])):
    mp = float(model.price(spot, o["strike"], T, r, sigma_hist, o["kind"], D))
    vol_i = iv.implied_vol(o["price"], spot, o["strike"], T, r, o["kind"], D)
    chain_out.append({**o, "model": mp, "iv": vol_i, "moneyness": o["strike"] / spot})
dropped = len(chain) - len(traded)

calls = [c for c in chain_out if c["kind"] == "call"]
puts = [c for c in chain_out if c["kind"] == "put"]


def bucket(c):
    m = c["moneyness"] if c["kind"] == "call" else 1 / c["moneyness"]
    return "ITM" if m < 0.97 else ("OTM" if m > 1.03 else "ATM")


md.append(f"\n## 4. Our model's prices vs NSE premiums\n\n{len(traded)} traded contracts "
          f"({dropped} dropped with volume < {config.MIN_VOLUME}: their 'prices' are stale).\n")
summary = []
for kind, group in (("call", calls), ("put", puts)):
    for b in ("ITM", "ATM", "OTM"):
        g = [c for c in group if bucket(c) == b]
        if g:
            err = np.array([c["model"] - c["price"] for c in g])
            pct = np.array([(c["model"] - c["price"]) / c["price"] for c in g])
            summary.append((f"{kind}s {b}", len(g), f"{err.mean():+.2f}", f"{np.abs(err).mean():.2f}", f"{np.median(pct):+.1%}"))
table(["Group", "Contracts", "Mean (model - market), Rs", "Mean abs error, Rs", "Median % error"], summary)
results["pricing_summary"] = summary

fig, axes = plt.subplots(1, 2, figsize=(13, 4.3))
for ax, group, name in ((axes[0], calls, "Calls"), (axes[1], puts, "Puts")):
    ks = [c["strike"] for c in group]
    ax.scatter(ks, [c["price"] for c in group], color=BLUE, s=22, label="NSE market premium", zorder=3)
    grid = np.linspace(min(strikes_all), max(strikes_all), 200)
    ax.plot(grid, model.price(spot, grid, T, r, sigma_hist, name[:-1].lower(), D), color=ORANGE,
            label=f"Our model, sigma = {sigma_hist:.1%}")
    ax.axvline(spot, color=INK_2, ls="--", lw=1)
    ax.set(title=f"{name}: model vs market (expiry {expiry})", xlabel="Strike", ylabel="Premium (Rs)")
    ax.legend()
save(fig, "fig4_model_vs_market.png", "Dashed line = spot. Gaps show where the market disagrees with our sigma")

ivs_otm = [c for c in chain_out if not np.isnan(c["iv"]) and
           ((c["kind"] == "put" and c["strike"] <= spot) or (c["kind"] == "call" and c["strike"] >= spot))]
atm_iv = min(ivs_otm, key=lambda c: abs(c["strike"] - spot))["iv"] if ivs_otm else float("nan")
results.update(atm_implied_vol=atm_iv, n_iv=len(ivs_otm))
fig, ax = plt.subplots(figsize=(10, 4.3))
for kind, col, name in (("put", ORANGE, "OTM puts (K below spot)"), ("call", BLUE, "OTM calls (K above spot)")):
    pts = sorted((c["strike"], c["iv"]) for c in ivs_otm if c["kind"] == kind)
    if pts:
        ax.plot(*zip(*pts), color=col, marker="o", ms=5, lw=1.4, label=f"{name}: implied vol (our solver)")
ax.axhline(sigma_hist, color=AQUA, ls="--", label=f"Our historical sigma {sigma_hist:.1%}")
ax.axvline(spot, color=INK_2, ls=":", lw=1)
ax.set(title="What sigma is the market using? Implied volatility by strike", xlabel="Strike", ylabel="Implied volatility")
ax.legend(loc="upper center")
save(fig, "fig5_implied_volatility.png", "Out-of-the-money options only: in-the-money premiums are mostly intrinsic value, so their implied vol is unreliable. Our model assumes one sigma for every strike.")
md.append(f"\nATM implied volatility = **{atm_iv:.2%}** vs our historical estimate {sigma_hist:.2%}. "
          "The full table is in chain.csv.\n")

# ======================================================= 5. parity ====
pairs = []
by_strike = {}
for c in chain_out:
    by_strike.setdefault(c["strike"], {})[c["kind"]] = c
for k, legs in sorted(by_strike.items()):
    if "call" in legs and "put" in legs:
        gap = legs["call"]["price"] - legs["put"]["price"] - (spot - D - k * np.exp(-r * T))
        pairs.append((k, gap))
md.append("\n## 5. Does the market obey put-call parity?\n\n"
          "c - p should equal S0 - D - K e^(-rT). Deviation per strike (Rs):\n")
if pairs:
    gaps = np.array([g for _, g in pairs])
    table(["Strikes with both legs traded", "Mean deviation", "Mean absolute deviation", "Largest absolute deviation", "Mean absolute as % of spot"],
          [(len(pairs), f"{gaps.mean():+.2f}", f"{np.abs(gaps).mean():.2f}", f"{np.abs(gaps).max():.2f}", f"{np.abs(gaps).mean()/spot:.3%}")])
    results["parity"] = {"n": len(pairs), "mean": gaps.mean(), "mean_abs": np.abs(gaps).mean()}

# ======================================================= 6. Greeks ====
lot = config.LOT_SIZE if not demo else 500
grid = np.array(sorted(by_strike))
g_call = gk.greeks(spot, grid, T, r, sigma_hist, "call", D)
g_put = gk.greeks(spot, grid, T, r, sigma_hist, "put", D)
fig, axes = plt.subplots(1, 4, figsize=(16, 3.8))
for ax, name, title in zip(axes, ("delta", "gamma", "theta", "vega"),
                           ("Delta (shares per lot)", "Gamma (per lot)", "Theta (Rs per day per lot)", "Vega (Rs per 1% vol per lot)")):
    ax.plot(grid, g_call[name] * lot, color=BLUE, label="Long call")
    if name in ("delta", "theta"):
        ax.plot(grid, g_put[name] * lot, color=ORANGE, label="Long put")
        ax.legend(fontsize=8)
    ax.axvline(spot, color=INK_2, ls=":", lw=1)
    ax.set(title=title, xlabel="Strike")
save(fig, "fig6_greeks_per_lot.png", f"Risk of one lot ({lot} shares) at each strike, from our model")

# ======================================================= 7. backtest ====
bt = hedging.backtest_short_call(dates, closes, r, config.VOL_WINDOW, config.BACKTEST_OPTION_DAYS)
hedged = np.array([b["hedged_pnl"] / b["S0"] for b in bt]) * 100
unhedged = np.array([b["unhedged_pnl"] / b["S0"] for b in bt]) * 100
gap_var = np.array([b["sigma_used"] ** 2 - b["realised_vol"] ** 2 for b in bt])
corr = float(np.corrcoef(gap_var, hedged)[0, 1]) if len(bt) > 2 else float("nan")
results["backtest"] = {"periods": len(bt), "hedged_mean_pct": hedged.mean(), "hedged_sd_pct": hedged.std(ddof=1),
                       "unhedged_mean_pct": unhedged.mean(), "unhedged_sd_pct": unhedged.std(ddof=1),
                       "hedged_win_rate": float((hedged > 0).mean()), "corr_with_vol_gap": corr}
md.append(f"\n## 6. Backtest: selling a 1-month ATM call at our price and delta-hedging it\n\n"
          f"{len(bt)} non-overlapping periods. Each starts with sigma = trailing {config.VOL_WINDOW}-day "
          "volatility (only information known that day) and rebalances at every daily close. "
          "P&L is per call sold, as % of the share price.\n")
table(["Seller's strategy", "Mean P&L", "Std of P&L", "Periods with profit", "Worst period"], [
    ("Delta-hedged (Black-Scholes)", f"{hedged.mean():+.3f}%", f"{hedged.std(ddof=1):.3f}%", f"{(hedged > 0).mean():.0%}", f"{hedged.min():+.2f}%"),
    ("Unhedged (just collect premium)", f"{unhedged.mean():+.3f}%", f"{unhedged.std(ddof=1):.3f}%", f"{(unhedged > 0).mean():.0%}", f"{unhedged.min():+.2f}%"),
])
md.append(f"\nCorrelation between hedged P&L and (sigma used^2 - realised vol^2): **{corr:+.2f}**. "
          "Black-Scholes predicts this should be strongly positive: the hedger gains when the share "
          "turns out calmer than the sigma charged, and loses when it is wilder.\n")

fig, axes = plt.subplots(1, 2, figsize=(13, 4.3))
bins = np.linspace(min(unhedged.min(), hedged.min()), max(unhedged.max(), hedged.max()), 40)
axes[0].hist(unhedged, bins=bins, color=ORANGE, alpha=0.45, label="Unhedged")
axes[0].hist(hedged, bins=bins, color=BLUE, alpha=0.6, label="Delta-hedged")
axes[0].set(title="Seller's P&L per period", xlabel="P&L (% of share price)", ylabel="Periods")
axes[0].legend()
axes[1].scatter([b["sigma_used"] for b in bt], [b["realised_vol"] for b in bt], color=BLUE, s=22, label="One period")
lim = [0, max(max(b["sigma_used"] for b in bt), max(b["realised_vol"] for b in bt)) * 1.1]
axes[1].plot(lim, lim, color=ORANGE, lw=1.5, label="Forecast = outcome")
axes[1].set(title="Our sigma forecast vs volatility that followed", xlabel="sigma used (trailing)", ylabel="Realised over option life", xlim=lim, ylim=lim)
axes[1].legend()
save(fig, "fig7_hedging_backtest.png", "Hedging shrinks the seller's risk; what remains comes from mis-forecast volatility")

# ======================================================= write ====
with open(OUT / "chain.csv", "w") as f:
    f.write("strike,type,market,model,implied_vol,volume,moneyness\n")
    for c in chain_out:
        f.write(f"{c['strike']},{c['kind']},{c['price']},{c['model']:.4f},{c['iv']:.6f},{c['volume']},{c['moneyness']:.4f}\n")
(OUT / "results.md").write_text("".join(md))
(OUT / "results.json").write_text(json.dumps(results, indent=2, default=str))
print(f"{'DEMO run' if demo else symbol}: wrote {OUT}/results.md, results.json, chain.csv and 7 figures")
