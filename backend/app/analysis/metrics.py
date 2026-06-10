"""Compute price-derived metrics from OHLCV history: current price, returns,
annualized volatility, beta vs EGX30, and average daily traded value (liquidity)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.data.sources import FetchResult, PriceHistory

TRADING_DAYS = 252


def _daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().dropna()


def _trailing_return(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    past, now = close.iloc[-days - 1], close.iloc[-1]
    if past and past == past and past != 0:
        return float(now / past - 1.0)
    return None


def compute_metrics(ph: PriceHistory, index_returns: pd.Series | None) -> dict:
    """Returns a dict of live metrics (may be partial if history is short/empty)."""
    out: dict = {"data_ok": ph.ok}
    if not ph.ok or ph.df.empty or "Close" not in ph.df:
        return out

    df = ph.df.dropna(subset=["Close"])
    close = df["Close"].astype(float)
    if close.empty:
        out["data_ok"] = False
        return out

    out["price"] = float(close.iloc[-1])
    out["last_date"] = str(df.index[-1].date())
    out["high_52w"] = float(close.tail(TRADING_DAYS).max())
    out["low_52w"] = float(close.tail(TRADING_DAYS).min())

    rets = _daily_returns(close)
    if len(rets) >= 20:
        out["volatility"] = float(rets.std() * math.sqrt(TRADING_DAYS))

    out["ret_1m"] = _trailing_return(close, 21)
    out["ret_3m"] = _trailing_return(close, 63)
    out["ret_6m"] = _trailing_return(close, 126)
    out["ret_1y"] = _trailing_return(close, TRADING_DAYS)

    # liquidity: average daily traded value over ~last 60 sessions, in EGP
    if "Volume" in df:
        traded = (close * df["Volume"].astype(float)).tail(60).dropna()
        if not traded.empty:
            out["avg_daily_value"] = float(traded.mean())

    # beta vs EGX30 (align on dates)
    if index_returns is not None and len(rets) >= 60:
        joined = pd.concat([rets.rename("s"), index_returns.rename("m")],
                           axis=1, join="inner").dropna()
        if len(joined) >= 60 and joined["m"].var() > 0:
            cov = np.cov(joined["s"], joined["m"])[0, 1]
            out["beta"] = float(cov / joined["m"].var())

    return out


MIN_INDEX_ROWS = 60


def market_returns(fetch: FetchResult) -> tuple[pd.Series | None, str]:
    """Daily market returns for beta. Prefer the real EGX30 index; if Yahoo's
    ^CASE30 is unusable (it frequently returns ~1 row), fall back to an
    equal-weight proxy built from the fetched universe itself.

    Returns (series, source_label).
    """
    idx = fetch.index
    if idx.ok and not idx.df.empty and "Close" in idx.df:
        rets = idx.df["Close"].astype(float).pct_change().dropna()
        if len(rets) >= MIN_INDEX_ROWS:
            return rets, "CASE30"

    # proxy: equal-weight mean of daily returns across all OK stocks
    cols = []
    for sym, ph in fetch.prices.items():
        if ph.ok and not ph.df.empty and "Close" in ph.df:
            cols.append(ph.df["Close"].astype(float).pct_change().rename(sym))
    if not cols:
        return None, "none"
    panel = pd.concat(cols, axis=1)
    proxy = panel.mean(axis=1, skipna=True).dropna()
    if len(proxy) < MIN_INDEX_ROWS:
        return None, "none"
    return proxy, "proxy_equalweight"


# kept for backwards-compat with older callers
def index_daily_returns(fetch: FetchResult) -> pd.Series | None:
    return market_returns(fetch)[0]


# Plausibility bands for LIVE fundamentals. Yahoo's EGX fundamentals are
# unreliable (e.g. trailingPE of 0.12); values outside these bands are rejected
# and we fall back to the curated static figure.
LIVE_BOUNDS = {
    "market_cap": (1e8, 5e12),
    "pe": (1.5, 150.0),
    "pb": (0.2, 30.0),
    "dividend_yield": (0.0, 0.30),
    "payout_ratio": (0.0, 1.5),
    "roe": (-1.0, 1.5),
    "beta": (-1.0, 4.0),
}


def _live_ok(field: str, value) -> bool:
    lo, hi = LIVE_BOUNDS.get(field, (float("-inf"), float("inf")))
    return lo <= value <= hi


def merge_fundamentals(static: dict, live: dict, computed: dict) -> dict:
    """Precedence: computed (price-derived) > validated live > static fallback.

    Live values that fail their plausibility band are skipped (Yahoo EGX data is
    noisy). Returns a flat dict plus a `provenance` map for transparency.
    """
    fields = ["market_cap", "pe", "pb", "dividend_yield", "payout_ratio",
              "roe", "eps_growth_3y", "beta"]
    merged: dict = {}
    provenance: dict = {}
    for f in fields:
        if f in computed and computed[f] is not None:
            merged[f], provenance[f] = computed[f], "computed"
        elif f in live and live[f] is not None and _live_ok(f, live[f]):
            merged[f], provenance[f] = live[f], "live"
        elif f in static and static[f] is not None:
            merged[f], provenance[f] = static[f], "static"
    # price-derived fields are always computed-or-missing
    for f in ["price", "volatility", "avg_daily_value", "high_52w", "low_52w",
              "ret_1m", "ret_3m", "ret_6m", "ret_1y", "last_date", "data_ok"]:
        if f in computed:
            merged[f] = computed[f]
    merged["provenance"] = provenance
    return merged
