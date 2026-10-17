"""Create FAKE data in NSE's file formats, so the pipeline can run before real data arrives.

The share is called DEMO. Its option prices are generated with a volatility
that varies by strike plus random noise, roughly like a real market.
Nothing produced from this data is a finding about any real stock.
"""
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ourbs.model import price  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "demo"
rng = np.random.default_rng(2026)


def trading_days(end, n):
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days[::-1]


def make_stock():
    dates = trading_days(date(2026, 10, 16), 3 * 252)
    rets = 0.25 / np.sqrt(252) * rng.standard_t(4, len(dates) - 1) / np.sqrt(2) + 0.10 / 252
    closes = 1400 * np.exp(np.concatenate([[0], np.cumsum(rets)]))
    (OUT / "stock").mkdir(parents=True, exist_ok=True)
    with open(OUT / "stock" / "DEMO_history.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date ", "series ", "OPEN ", "HIGH ", "LOW ", "PREV. CLOSE ", "ltp ", "close "])
        prev = closes[0]
        for d, c in zip(dates, closes):
            w.writerow([d.strftime("%d-%b-%Y"), "EQ", f"{prev:,.2f}", f"{max(prev, c):,.2f}",
                        f"{min(prev, c):,.2f}", f"{prev:,.2f}", f"{c:,.2f}", f"{c:,.2f}"])
            prev = c
    return dates[-1], closes[-1]


def make_bhavcopy(trade_date, spot, r=0.055):
    cols = ["TradDt", "BizDt", "Sgmt", "Src", "FinInstrmTp", "FinInstrmId", "ISIN", "TckrSymb",
            "SctySrs", "XpryDt", "FininstrmActlXpryDt", "StrkPric", "OptnTp", "FinInstrmNm",
            "OpnPric", "HghPric", "LwPric", "ClsPric", "LastPric", "PrvsClsgPric", "UndrlygPric",
            "SttlmPric", "OpnIntrst", "ChngInOpnIntrst", "TtlTradgVol", "TtlTrfVal",
            "TtlNbOfTxsExctd", "SsnId", "NewBrdLotQty", "Rmks", "Rsvd1", "Rsvd2", "Rsvd3", "Rsvd4"]
    rows = []
    for expiry in (date(2026, 10, 27), date(2026, 11, 24)):
        T = (expiry - trade_date).days / 365
        for K in np.arange(round(spot * 0.8 / 20) * 20, spot * 1.2, 20):
            for code, kind in (("CE", "call"), ("PE", "put")):
                m = np.log(K / spot)
                vol = 0.24 - 0.25 * m + 0.6 * m**2 + rng.normal(0, 0.004)
                p = float(price(spot, K, T, r, vol, kind))
                p = max(round(p * (1 + rng.normal(0, 0.01)) / 0.05) * 0.05, 0.05)
                volume = int(rng.poisson(4000 * np.exp(-30 * m * m))) if rng.random() > 0.1 else 0
                row = dict.fromkeys(cols, "")
                row.update(TradDt=trade_date.isoformat(), BizDt=trade_date.isoformat(), Sgmt="FO",
                           Src="NSE", FinInstrmTp="STO", TckrSymb="DEMO", XpryDt=expiry.isoformat(),
                           StrkPric=f"{K:.1f}", OptnTp=code, ClsPric=f"{p:.2f}", LastPric=f"{p:.2f}",
                           UndrlygPric=f"{spot:.2f}", SttlmPric=f"{p:.2f}",
                           OpnIntrst=str(volume * 3), TtlTradgVol=str(volume), NewBrdLotQty="500")
                rows.append(row)
    rows.append(dict(dict.fromkeys(cols, ""), TradDt=trade_date.isoformat(), FinInstrmTp="IDO",
                     TckrSymb="NIFTY", XpryDt="2026-10-20", StrkPric="25000", OptnTp="CE",
                     ClsPric="100", UndrlygPric="25000", OpnIntrst="1", TtlTradgVol="1"))
    (OUT / "options").mkdir(parents=True, exist_ok=True)
    with open(OUT / "options" / f"BhavCopy_NSE_FO_{trade_date:%Y%m%d}_DEMO.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    last_date, last_close = make_stock()
    make_bhavcopy(last_date, float(last_close))
    print(f"Demo data written to {OUT} (last close {last_close:.2f} on {last_date})")
