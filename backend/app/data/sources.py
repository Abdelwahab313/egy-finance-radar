"""Data-source abstraction. yfinance is the free default for EGX (.CA suffix).

Swap in EODHD (.EGX, paid) later by implementing `DataSource` — nothing else changes.

`MarksOverlaySource` wraps any other source with the owner's dated broker marks
(``data/marks.json``). It is deliberately the *only* second opinion here: adding
another scraped vendor would add another thing that lags, freezes or 403s, while
the broker screen is the one EGX price the owner can always read.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from app import config
from app.data.marks import Mark, load_marks, relative_gap
from app.data.universe import yahoo_ticker


@dataclass
class PriceHistory:
    symbol: str
    df: pd.DataFrame                       # index=date, cols: Open High Low Close Volume
    ok: bool = True
    error: str | None = None


@dataclass
class IndexHistory:
    df: pd.DataFrame                       # cols include Close
    ok: bool = True
    error: str | None = None


@dataclass
class FetchResult:
    prices: dict[str, PriceHistory]
    index: IndexHistory
    live_info: dict[str, dict] = field(default_factory=dict)   # symbol -> partial fundamentals
    marks: dict = field(default_factory=dict)                  # what MarksOverlaySource did


class DataSource(ABC):
    @abstractmethod
    def fetch(self, symbols: list[str]) -> FetchResult: ...


class YFinanceSource(DataSource):
    """Free EGX data via Yahoo. Liquid index names only; flaky on thin tickers."""

    def __init__(self, period: str = config.HISTORY_LOOKBACK):
        self.period = period

    def fetch(self, symbols: list[str]) -> FetchResult:
        import yfinance as yf

        prices: dict[str, PriceHistory] = {}
        live_info: dict[str, dict] = {}

        for sym in symbols:
            yt = yahoo_ticker(sym)
            try:
                tk = yf.Ticker(yt)
                hist = tk.history(period=self.period, auto_adjust=False)
                if hist is None or hist.empty:
                    prices[sym] = PriceHistory(sym, pd.DataFrame(), ok=False,
                                               error="empty history")
                    continue
                prices[sym] = PriceHistory(sym, hist)
                live_info[sym] = self._extract_info(tk)
            except Exception as exc:  # network / backend flakiness
                prices[sym] = PriceHistory(sym, pd.DataFrame(), ok=False, error=str(exc))

        index = self._fetch_index()
        return FetchResult(prices=prices, index=index, live_info=live_info)

    def _fetch_index(self) -> IndexHistory:
        import yfinance as yf
        try:
            df = yf.Ticker(config.EGX30_INDEX).history(period=self.period,
                                                       auto_adjust=False)
            if df is None or df.empty:
                return IndexHistory(pd.DataFrame(), ok=False, error="empty index")
            return IndexHistory(df)
        except Exception as exc:
            return IndexHistory(pd.DataFrame(), ok=False, error=str(exc))

    @staticmethod
    def _extract_info(tk) -> dict:
        """Best-effort live fundamentals; EGX coverage is partial, so guard everything."""
        out: dict = {}
        try:
            info = tk.info or {}
        except Exception:
            return out
        mapping = {
            "market_cap": "marketCap",
            "pe": "trailingPE",
            "pb": "priceToBook",
            "dividend_yield": "dividendYield",
            "payout_ratio": "payoutRatio",
            "roe": "returnOnEquity",
            "beta": "beta",
        }
        for our, theirs in mapping.items():
            v = info.get(theirs)
            if isinstance(v, (int, float)) and v == v:  # not NaN
                # Yahoo sometimes reports dividendYield as a percent (e.g. 4.0 -> 0.04)
                if our == "dividend_yield" and v > 1:
                    v = v / 100.0
                out[our] = float(v)
        return out


class MarksOverlaySource(DataSource):
    """Wrap another source and let the owner's dated broker marks have the last word.

    Applied per symbol, after the inner fetch:

    * mark newer than the vendor's last bar -> append it as the latest bar and
      report ``vendor_lag_days``. Volume is NaN, which ``metrics`` already drops,
      so avg-traded-value is computed from real vendor volume only.
    * mark on the same date as a vendor bar -> compare, never overwrite. A gap
      above ``config.MARK_CONFLICT_PCT`` is a screening-rule-4 conflict: nobody
      agrees on the price, so the name is not orderable until reconciled.
    * mark older than the vendor's last bar -> ignored; the vendor has caught up.
    * no vendor history at all -> unapplied. A mark cannot invent a series.
    """

    def __init__(self, inner: DataSource, marks: dict[str, Mark] | None = None,
                 today: date | None = None):
        self.inner = inner
        self.marks = load_marks() if marks is None else marks
        self.today = today or date.today()

    def fetch(self, symbols: list[str]) -> FetchResult:
        result = self.inner.fetch(symbols)
        applied: list[dict] = []
        conflicts: list[dict] = []
        unapplied: list[dict] = []

        for sym in symbols:
            mark = self.marks.get(sym)
            if mark is None:
                continue
            ph = result.prices.get(sym)
            if ph is None or not ph.ok or ph.df.empty:
                unapplied.append({"symbol": sym, "as_of": str(mark.as_of),
                                  "price": mark.price, "source": mark.source,
                                  "reason": "no vendor history to overlay"})
                continue

            last_date = ph.df.index[-1].date()
            last_close = float(ph.df["Close"].iloc[-1])
            gap = relative_gap(mark.price, last_close)
            row = {"symbol": sym, "mark": mark.price, "as_of": str(mark.as_of),
                   "source": mark.source, "vendor_last_close": round(last_close, 4),
                   "vendor_last_date": str(last_date), "gap_pct": round(gap * 100, 2),
                   "mark_age_days": mark.age_days(self.today)}

            if mark.as_of > last_date:
                result.prices[sym] = PriceHistory(sym, self._append_bar(ph.df, mark))
                row["action"] = "appended"
                row["vendor_lag_days"] = (mark.as_of - last_date).days
                applied.append(row)
            elif mark.as_of == last_date and gap > config.MARK_CONFLICT_PCT:
                row["action"] = "conflict"
                conflicts.append(row)
            else:
                row["action"] = "ignored (vendor is current)"
                unapplied.append(row)

        result.marks = {
            "path": config.MARKS_PATH,
            "conflict_threshold_pct": config.MARK_CONFLICT_PCT * 100,
            "applied": applied,
            "conflicts": conflicts,
            "unapplied": unapplied,
            "stale": [a for a in applied
                      if a["mark_age_days"] > config.MARK_MAX_AGE_DAYS],
        }
        for c in conflicts:
            print(f"[marks] CONFLICT {c['symbol']}: mark {c['mark']} vs vendor "
                  f"{c['vendor_last_close']} on {c['vendor_last_date']} "
                  f"({c['gap_pct']}% apart) — rule 4, not orderable until reconciled")
        for a in applied:
            print(f"[marks] {a['symbol']:6} <- {a['mark']} ({a['as_of']}, {a['source']}); "
                  f"vendor was {a['vendor_last_close']} on {a['vendor_last_date']} "
                  f"({a['vendor_lag_days']}d behind, {a['gap_pct']}% apart)")
        return result

    @staticmethod
    def _append_bar(df: pd.DataFrame, mark: Mark) -> pd.DataFrame:
        """Append the mark as one bar. Volume is NaN on purpose: we know the price
        the owner read, we do not know the day's turnover, and inventing a 0 would
        quietly drag the 60-session avg-traded-value gate down."""
        bar = {c: float("nan") for c in df.columns}
        for col in ("Open", "High", "Low", "Close"):
            if col in bar:
                bar[col] = mark.price
        stamp = pd.Timestamp(mark.as_of)
        if df.index.tz is not None:
            stamp = stamp.tz_localize(df.index.tz)
        return pd.concat([df, pd.DataFrame([bar], index=[stamp])])
