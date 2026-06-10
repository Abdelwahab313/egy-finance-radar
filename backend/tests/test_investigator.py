"""Tests for the single-ticker investigation agent (deterministic layer + guards).

The yfinance network call is replaced with a synthetic source so these run offline.
"""

from datetime import date

import numpy as np
import pandas as pd

from app.agent import investigator
from app.data.sources import FetchResult, IndexHistory, PriceHistory


def _ohlcv(start: float, n: int = 300) -> pd.DataFrame:
    close = pd.Series(np.linspace(start, start * 1.2, n), dtype=float)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "Open": close.values,
        "High": (close * 1.01).values,
        "Low": (close * 0.99).values,
        "Close": close.values,
        "Volume": np.full(n, 5_000_000.0),
    }, index=idx)


class _FakeSource:
    """Stand-in for YFinanceSource — returns synthetic OHLCV for every symbol."""

    def __init__(self, *args, **kwargs):
        pass

    def fetch(self, syms):
        prices = {s: PriceHistory(s, _ohlcv(50 + 5 * i)) for i, s in enumerate(syms)}
        return FetchResult(prices=prices, index=IndexHistory(_ohlcv(1000)), live_info={})


def test_normalize_symbol():
    assert investigator.normalize_symbol(" comi ") == "COMI"
    assert investigator.normalize_symbol("elsh.ca") == "ELSH"


def test_analyze_ticker_returns_required_keys(monkeypatch):
    monkeypatch.setattr(investigator, "YFinanceSource", _FakeSource)
    out = investigator.analyze_ticker("comi")  # curated universe name, lowercased

    assert out["symbol"] == "COMI"
    for k in ("symbol", "as_of", "in_universe", "target", "peers", "data_quality"):
        assert k in out, f"missing top-level key {k}"
    assert out["in_universe"] is True

    target = out["target"]
    for k in ("symbol", "name", "bucket", "score", "eligible", "metrics", "signal"):
        assert k in target, f"missing target key {k}"
    assert isinstance(target["score"], float)

    peers = out["peers"]
    assert peers["universe_size"] >= 1
    assert "bucket_medians" in peers and "universe_medians" in peers


def test_analyze_ticker_handles_unknown_symbol(monkeypatch):
    monkeypatch.setattr(investigator, "YFinanceSource", _FakeSource)
    out = investigator.analyze_ticker("ELSH")  # not in the curated universe
    assert out["in_universe"] is False
    assert out["target"]["symbol"] == "ELSH"
    # peers are still the universe (target excluded), so comparison is populated
    assert out["peers"]["universe_size"] >= 1


def test_investigate_returns_cached_when_report_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(investigator, "REPORTS_DIR", str(tmp_path))
    fn = f"COMI_{date.today().isoformat()}.md"
    (tmp_path / fn).write_text("# cached report")

    out = investigator.investigate("COMI")  # must NOT spawn the headless agent
    assert out["status"] == "done"
    assert out["cached"] is True
    assert out["filename"] == fn


def test_report_filename_regex_rejects_traversal():
    from app.main import REPORT_FILENAME_RE

    assert REPORT_FILENAME_RE.match("ELSH_2026-06-08.md")
    assert not REPORT_FILENAME_RE.match("../etc/passwd")
    assert not REPORT_FILENAME_RE.match("../ELSH_2026-06-08.md")
    assert not REPORT_FILENAME_RE.match("elsh_2026-06-08.md")   # lowercase symbol
    assert not REPORT_FILENAME_RE.match("ELSH_2026-06-08.txt")  # wrong extension
