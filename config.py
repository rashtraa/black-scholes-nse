"""Project settings. Edit these, then run `python analysis.py`."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent

# ---- Which stock --------------------------------------------------------
SYMBOL = "RELIANCE"            # NSE symbol, exactly as in the bhavcopy
LOT_SIZE = 500                 # from the bhavcopy (NewBrdLotQty) for 16-Oct-2026

# ---- Data folders (see data/README.md for what to download) -------------
STOCK_DIR = ROOT / "data" / "stock"       # share price history CSVs
OPTIONS_DIR = ROOT / "data" / "options"   # bhavcopy / option chain / template CSVs
USE_DEMO_IF_EMPTY = True                  # fall back to data/demo when the folders are empty

# ---- Market inputs -------------------------------------------------------
RISK_FREE_RATE = 0.056876      # 91-day T-bill 5.7281% (RBI), converted to continuous compounding
TRADE_DATE = None              # date to analyse, e.g. date(2026, 10, 16); None = latest in the data
EXPIRY = date(2026, 11, 23)    # November contract: 38 days left. The Oct contract (11 days) has so
                               # little time value that tiny price ticks swamp the comparison.
                               # Set None for the nearest expiry, or date(2026, 12, 29).
DIVIDENDS = []                 # ex-dividend dates inside the option's life: [(date(2026, 8, 14), 5.5)]
                               # RELIANCE: last ex-date 05-Jun-2026, none before these expiries.

# Bonus issues and splits make the raw share price drop overnight. Prices before
# the ex-date are divided by the factor (bonus 1:1 -> 2, split 1-for-5 -> 5).
CORPORATE_ACTIONS = [(date(2024, 10, 28), 2.0)]   # RELIANCE bonus 1:1

# Only needed if you use the option-chain page's CSV (it doesn't record these):
OPTION_CHAIN = {"date": None, "expiry": None, "spot": None}

# ---- Model choices -------------------------------------------------------
VOL_WINDOW = 63                # trading days of history used to estimate sigma (~3 months)
MIN_VOLUME = 1                 # ignore strikes that did not trade (stale prices)
BACKTEST_OPTION_DAYS = 21      # life of each option in the hedging backtest (~1 month)
