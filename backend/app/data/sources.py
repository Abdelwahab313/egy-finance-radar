"""Data-source abstraction. yfinance is the free default for EGX (.CA suffix).

Swap in EODHD (.EGX, paid) later by implementing `DataSource` — nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd

from app import config
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
