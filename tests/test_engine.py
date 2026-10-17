"""Checks that our engine is internally consistent and mathematically right.

These are not textbook examples: each test checks a property the model must
satisfy, using independent routes to the same number.
"""
import csv
from datetime import date

import numpy as np
import pytest

from ourbs import binomial, greeks, hedging, implied_vol, model, normal, simulation, volatility
from ourbs.nse_data import load_options, load_stock_history

approx = pytest.approx
S, K, T, r, SIG = 1450.0, 1500.0, 30 / 365, 0.055, 0.24


# ---- our normal distribution ------------------------------------------------
@pytest.mark.parametrize("x", [-3.5, -1.2, -0.3, 0.0, 0.7, 1.96, 4.0])
def test_cdf_matches_numerical_integration(x):
    assert normal.cdf(x) == approx(normal.cdf_by_integration(x), abs=1e-7)


def test_cdf_symmetry_and_limits():
    xs = np.linspace(-5, 5, 41)
    assert np.allclose(normal.cdf(xs) + normal.cdf(-xs), 1.0)
    assert normal.cdf(-12) < 1e-12 and normal.cdf(12) > 1 - 1e-12
    assert np.all(np.diff(normal.cdf(xs)) > 0)


def test_inverse_cdf_round_trip():
    p = np.array([0.001, 0.05, 0.5, 0.8, 0.999])
    assert np.allclose(normal.cdf(normal.inverse_cdf(p)), p, atol=1e-9)


def test_box_muller_draws_are_standard_normal():
    z = normal.standard_normal_draws(400_000, seed=3)
    assert z.mean() == approx(0, abs=0.01)
    assert z.std() == approx(1, abs=0.01)
    assert np.mean(z < 1.0) == approx(normal.cdf(1.0), abs=0.003)


# ---- the pricing model -------------------------------------------------------
@pytest.mark.parametrize("D", [0.0, 12.5])
def test_put_call_parity(D):
    strikes = np.linspace(1200, 1700, 11)
    c = model.call_price(S, strikes, T, r, SIG, D)
    p = model.put_price(S, strikes, T, r, SIG, D)
    assert np.allclose(c - p, S - D - strikes * np.exp(-r * T), atol=1e-6)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_binomial_tree_converges_to_formula(kind):
    tree = binomial.crr_price(S, K, T, r, SIG, kind, steps=2000)
    assert tree == approx(float(model.price(S, K, T, r, SIG, kind)), abs=0.02)


def test_monte_carlo_agrees_within_its_confidence_interval():
    res = simulation.mc_price(S, K, T, r, SIG, "call", n=400_000, seed=11)
    lo, hi = res["ci_95"]
    assert lo < float(model.call_price(S, K, T, r, SIG)) < hi


def test_prices_respect_no_arbitrage_bounds():
    for k in (1000, 1450, 2000):
        for kind in ("call", "put"):
            lo, hi = model.no_arbitrage_bounds(S, k, T, r, kind)
            assert lo - 1e-9 <= float(model.price(S, k, T, r, SIG, kind)) <= hi + 1e-9


def test_zero_volatility_leaves_discounted_intrinsic_value():
    assert float(model.call_price(S, 1400, T, r, 1e-8)) == approx(S - 1400 * np.exp(-r * T), abs=1e-6)
    assert float(model.put_price(S, 1400, T, r, 1e-8)) == approx(0, abs=1e-6)


# ---- Greeks ------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["call", "put"])
def test_greeks_match_bump_and_reprice(kind):
    f = lambda S=S, T=T, r=r, v=SIG: float(model.price(S, K, T, r, v, kind))
    g = greeks.greeks(S, K, T, r, SIG, kind)
    h = 0.01
    assert g["delta"] == approx((f(S=S + h) - f(S=S - h)) / (2 * h), rel=1e-5)
    assert g["gamma"] == approx((f(S=S + 1) - 2 * f() + f(S=S - 1)) / 1, rel=1e-3)
    assert g["vega"] == approx((f(v=SIG + 1e-4) - f(v=SIG - 1e-4)) / 2e-4 / 100, rel=1e-4)
    assert g["rho"] == approx((f(r=r + 1e-4) - f(r=r - 1e-4)) / 2e-4 / 100, rel=1e-4)
    assert g["theta"] == approx(f(T=T - 1 / 365) - f(), rel=0.02)


# ---- implied volatility ------------------------------------------------------
@pytest.mark.parametrize("k,kind", [(1200, "put"), (1400, "put"), (1450, "call"), (1600, "call"), (1800, "call")])
@pytest.mark.parametrize("sigma", [0.12, 0.3, 0.8])
def test_implied_vol_recovers_sigma(k, kind, sigma):
    p = float(model.price(S, k, T, r, sigma, kind))
    if p < 0.05:          # below NSE's tick size: no information left in the price
        pytest.skip("price below one tick")
    assert implied_vol.implied_vol(p, S, k, T, r, kind) == approx(sigma, abs=1e-5)


def test_implied_vol_is_nan_for_arbitrage_prices():
    assert np.isnan(implied_vol.implied_vol(1.0, S, 1300, T, r, "call"))   # below intrinsic


# ---- volatility and hedging ----------------------------------------------------
def test_historical_vol_recovers_true_sigma():
    z = normal.standard_normal_draws(252 * 20, seed=5)
    closes = 100 * np.exp(np.cumsum(0.3 / np.sqrt(252) * z))
    assert volatility.annualised_vol(volatility.log_returns(closes)) == approx(0.3, abs=0.01)


def test_delta_hedge_is_nearly_riskless_when_model_is_true():
    z = normal.standard_normal_draws(252 * 30, seed=9)
    closes = 1000 * np.exp(np.cumsum(0.25 / np.sqrt(252) * z + 0.0004))
    dates = list(range(len(closes)))
    bt = hedging.backtest_short_call(dates, closes, 0.05, vol_window=252, life_days=21)
    hedged = np.array([b["hedged_pnl"] for b in bt])
    unhedged = np.array([b["unhedged_pnl"] for b in bt])
    assert hedged.std() < 0.3 * unhedged.std()


# ---- data loading --------------------------------------------------------------
def test_reads_nse_formats(tmp_path):
    (tmp_path / "stock").mkdir()
    (tmp_path / "opt").mkdir()
    with open(tmp_path / "stock" / "a.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date ", "series ", "PREV. CLOSE ", "close "])
        w.writerow(["17-Oct-2026", "EQ", "1,440.00", "1,450.50"])
        w.writerow(["16-Oct-2026", "EQ", "1,430.00", "1,440.00"])
        w.writerow(["16-Oct-2026", "BL", "1,430.00", "9.99"])
    dates, closes = load_stock_history(tmp_path / "stock")
    assert dates == [date(2026, 10, 16), date(2026, 10, 17)] and closes == [1440.0, 1450.5]

    with open(tmp_path / "opt" / "chain.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["CALLS", "", "", "PUTS"])
        w.writerow(["", "OI", "VOLUME", "IV", "LTP", "BID", "ASK", "STRIKE", "BID", "ASK", "LTP", "IV", "VOLUME", "OI", ""])
        w.writerow(["", "1,000", "250", "22.1", "61.20", "61", "61.4", "1,400.00", "8.1", "8.3", "8.20", "24.0", "300", "900", ""])
        w.writerow(["", "-", "-", "-", "-", "-", "-", "1,500.00", "-", "-", "55.00", "-", "10", "-", ""])
    snap = {"date": date(2026, 10, 17), "expiry": date(2026, 10, 27), "spot": 1450.5}
    recs = load_options(tmp_path / "opt", "RELIANCE", snap)
    call = next(x for x in recs if x["kind"] == "call")
    put = next(x for x in recs if x["kind"] == "put" and x["strike"] == 1400)
    assert (call["strike"], call["price"], call["volume"], call["bid"]) == (1400, 61.2, 250, 61)
    assert (put["price"], put["volume"], put["ask"]) == (8.2, 300, 8.3)
    assert len(recs) == 3      # the call with no trades ('-') is dropped


def test_bonus_adjustment_removes_the_fake_crash():
    dates = [date(2024, 10, d) for d in (24, 25, 28, 29)]
    raw = [2700.0, 2740.0, 1365.0, 1380.0]          # 1:1 bonus, ex-date 28 Oct
    adj, notes = volatility.adjust_for_corporate_actions(dates, raw, [(date(2024, 10, 28), 2.0)])
    assert np.allclose(adj, [1350, 1370, 1365, 1380])
    assert not volatility.suspicious_jumps(dates, adj)
    already, notes = volatility.adjust_for_corporate_actions(dates, adj, [(date(2024, 10, 28), 2.0)])
    assert np.allclose(already, adj) and "already adjusted" in notes[0]
