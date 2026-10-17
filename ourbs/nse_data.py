"""Read NSE downloads with Python's csv module (no pandas).

Share prices : nseindia.com -> Get Quote -> Historical Data -> download CSV.
               Several yearly files can sit in the same folder; they are merged.
Option prices: any of
  * F&O bhavcopy (end-of-day, all contracts; old or new 'UDiFF' format)
  * the option-chain page's 'Download (.csv)' (a live snapshot)
  * our simple template: date, expiry, strike, type, price[, volume, underlying]
"""
import csv
from datetime import date, datetime
from pathlib import Path

DATE_FORMATS = ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%Y%m%d")


def parse_date(text):
    text = str(text).strip().strip('"')
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date: {text!r}")


def parse_number(text):
    text = str(text).replace(",", "").replace('"', "").strip()
    if text in ("", "-", "--", "nan", "NaN", "None"):
        return None
    return float(text)


def _rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [row for row in csv.reader(f) if any(cell.strip() for cell in row)]


def _norm(name):
    return name.replace("﻿", "").strip().strip('"').lower()


# --------------------------------------------------------------------------
# Share price history
# --------------------------------------------------------------------------
def load_stock_history(folder):
    """Return (dates, closes) sorted oldest first, merged across all CSVs in folder."""
    by_date = {}
    for path in sorted(Path(folder).glob("*.csv")):
        rows = _rows(path)
        header = [_norm(h) for h in rows[0]]
        date_col = next(i for i, h in enumerate(header) if h in ("date", "timestamp", "trade date"))
        close_col = next(i for i, h in enumerate(header)
                         if h in ("close", "close price", "closeprice", "adj close", "clspric"))
        series_col = next((i for i, h in enumerate(header) if h == "series"), None)
        for row in rows[1:]:
            if series_col is not None and row[series_col].strip() not in ("EQ", "BE"):
                continue
            close = parse_number(row[close_col])
            if close:
                by_date[parse_date(row[date_col])] = close
    if not by_date:
        raise FileNotFoundError(f"no share-price CSVs found in {folder}")
    dates = sorted(by_date)
    return dates, [by_date[d] for d in dates]


# --------------------------------------------------------------------------
# Option prices
# --------------------------------------------------------------------------
def _record(trade_date, expiry, strike, kind, price, volume=None, oi=None,
            underlying=None, bid=None, ask=None, source=""):
    return {"date": trade_date, "expiry": expiry, "strike": strike, "kind": kind,
            "price": price, "volume": volume, "oi": oi, "underlying": underlying,
            "bid": bid, "ask": ask, "source": source}


def _kind(code):
    code = code.strip().upper()
    return {"CE": "call", "C": "call", "CALL": "call", "PE": "put", "P": "put", "PUT": "put"}[code]


def _load_udiff_bhavcopy(rows, symbol, src):
    h = {_norm(name): i for i, name in enumerate(rows[0])}
    out = []
    for row in rows[1:]:
        if row[h["tckrsymb"]].strip() != symbol or row[h["fininstrmtp"]].strip() != "STO":
            continue
        out.append(_record(parse_date(row[h["traddt"]]), parse_date(row[h["xprydt"]]),
                           parse_number(row[h["strkpric"]]), _kind(row[h["optntp"]]),
                           parse_number(row[h["clspric"]]), parse_number(row[h["ttltradgvol"]]),
                           parse_number(row[h["opnintrst"]]), parse_number(row[h["undrlygpric"]]),
                           source=src))
    return out


def _load_old_bhavcopy(rows, symbol, src):
    h = {_norm(name): i for i, name in enumerate(rows[0])}
    out = []
    for row in rows[1:]:
        if row[h["symbol"]].strip() != symbol or row[h["instrument"]].strip() != "OPTSTK":
            continue
        out.append(_record(parse_date(row[h["timestamp"]]), parse_date(row[h["expiry_dt"]]),
                           parse_number(row[h["strike_pr"]]), _kind(row[h["option_typ"]]),
                           parse_number(row[h["close"]]), parse_number(row[h["contracts"]]),
                           parse_number(row[h["open_int"]]), source=src))
    return out


def _load_option_chain(rows, snapshot, src):
    """The option-chain page CSV: calls on the left of STRIKE, puts on the right."""
    head_idx = next(i for i, row in enumerate(rows) if any(_norm(c) == "strike" for c in row))
    header = [_norm(c) for c in rows[head_idx]]
    k = header.index("strike")
    left = {name: i for i, name in reversed(list(enumerate(header[:k])))}
    right = {}
    for i, name in enumerate(header[k + 1:], start=k + 1):
        right.setdefault(name, i)
    out = []
    for row in rows[head_idx + 1:]:
        strike = parse_number(row[k]) if len(row) > k else None
        if strike is None:
            continue
        for kind, cols in (("call", left), ("put", right)):
            get = lambda name: parse_number(row[cols[name]]) if name in cols else None
            out.append(_record(snapshot["date"], snapshot["expiry"], strike, kind, get("ltp"),
                               get("volume"), get("oi"), snapshot["spot"], get("bid"), get("ask"), src))
    return out


def _load_template(rows, src):
    h = {_norm(name): i for i, name in enumerate(rows[0])}
    opt = lambda row, name: parse_number(row[h[name]]) if name in h and h[name] < len(row) else None
    return [_record(parse_date(row[h["date"]]), parse_date(row[h["expiry"]]),
                    parse_number(row[h["strike"]]), _kind(row[h["type"]]),
                    parse_number(row[h["price"]]), opt(row, "volume"), opt(row, "oi"),
                    opt(row, "underlying"), opt(row, "bid"), opt(row, "ask"), src)
            for row in rows[1:]]


def load_options(folder, symbol, chain_snapshot=None):
    """All option records for `symbol` from every CSV in folder.

    chain_snapshot = {"date": date, "expiry": date, "spot": float} is needed for
    option-chain page downloads, which do not record these themselves.
    """
    records = []
    for path in sorted(Path(folder).glob("*.csv")):
        rows = _rows(path)
        first = {_norm(c) for c in rows[0]}
        if "tckrsymb" in first:
            records += _load_udiff_bhavcopy(rows, symbol, path.name)
        elif "strike_pr" in first:
            records += _load_old_bhavcopy(rows, symbol, path.name)
        elif {"strike", "type", "price"} <= first:
            records += _load_template(rows, path.name)
        elif any(_norm(c) == "strike" for row in rows[:3] for c in row):
            if not chain_snapshot or not all(chain_snapshot.get(k) for k in ("date", "expiry", "spot")):
                raise ValueError(f"{path.name} is an option-chain download: set OPTION_CHAIN "
                                 "date, expiry and spot in config.py")
            records += _load_option_chain(rows, chain_snapshot, path.name)
        else:
            raise ValueError(f"could not recognise the format of {path.name}")
    return [r for r in records if r["price"] is not None and r["strike"] is not None]
