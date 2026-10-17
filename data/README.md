# What data to download

All of it is free from nseindia.com. NSE renames menus from time to time, so
the paths below may differ slightly.

## 1. Share price history → `data/stock/`

1. On nseindia.com, search your stock (e.g. RELIANCE) to open its quote page.
2. Open **Historical Data** (under Trade Information), choose series **EQ**,
   pick a date range and click **Download (.csv)**.
3. Get **3 years**. NSE limits each download to about one year, so download
   three files and put all of them in `data/stock/`. The loader merges them
   and removes duplicate dates.

## 2. Option prices → `data/options/` (pick one)

**A. F&O bhavcopy (recommended).** This is NSE's end-of-day file with every
F&O contract, and it includes the underlying price.

- Go to Market Data → All Reports → Derivatives → **F&O - UDiFF Common
  Bhavcopy Final**, choose a trading day and download the zip.
- Unzip it and put the CSV in `data/options/`.
- The code keeps only your stock's options (`FinInstrmTp = STO`). It also
  reads the older bhavcopy format (`fo<date>bhav.csv`).

**B. Option chain page.** This is a live snapshot.

- Open nseindia.com/option-chain, choose your stock and the expiry, then
  click **Download (.csv)**.
- This file does not record the date, expiry or spot price. Note them from
  the page and fill in `OPTION_CHAIN` in `config.py`.

**C. Our template.** Use this if A and B don't work. Type the prices in by hand:

```
date,expiry,strike,type,price,volume,underlying
2026-10-16,2026-10-27,1400,CE,61.20,250,1450.50
2026-10-16,2026-10-27,1400,PE,8.20,300,1450.50
```

## 3. Other inputs → `config.py`

- `SYMBOL` and `LOT_SIZE`: check the lot size on NSE, because lot sizes are
  revised.
- `RISK_FREE_RATE`: the latest 91-day T-bill yield (RBI or CCIL website).
- `DIVIDENDS`: any ex-dividend date between the trade date and expiry (check
  the stock's Corporate Actions page on NSE).

Then run `python analysis.py`. Results go to `output/<SYMBOL>/`.
While `data/stock/` is empty, the pipeline runs on the fake `data/demo/` files instead.
