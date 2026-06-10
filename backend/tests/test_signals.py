"""Sanity checks for the technical/momentum signal engine."""

import numpy as np
import pandas as pd

from app.analysis.signals import compute_signal


def _ohlcv(closes):
    close = pd.Series(closes, dtype=float)
    return pd.DataFrame({
        "Open": close,
        "High": close * 1.01,
        "Low": close * 0.99,
        "Close": close,
        "Volume": np.full(len(close), 1_000_000.0),
    })


def test_uptrend_is_bullish():
    df = _ohlcv(np.linspace(100, 220, 260))      # steady rise
    out = compute_signal(df)
    assert out["signal"] in {"BUY", "HOLD", "TRIM"}   # never EXIT/AVOID in an uptrend
    assert out["indicators"]["trend"] == "up"
    assert out["levels"]["stop_loss"] is not None


def test_downtrend_exits_or_avoids():
    df = _ohlcv(np.linspace(220, 100, 260))      # steady decline
    out = compute_signal(df)
    assert out["signal"] in {"EXIT", "AVOID"}
    assert out["indicators"]["trend"] in {"down", "neutral"}


def test_insufficient_history():
    df = _ohlcv(np.linspace(100, 110, 20))
    assert compute_signal(df)["signal"] == "INSUFFICIENT_HISTORY"


def test_stop_below_price_and_target_above():
    df = _ohlcv(np.linspace(100, 220, 260))
    lv = compute_signal(df)["levels"]
    assert lv["stop_loss"] < lv["entry_zone"][1]
    if lv["take_profit"] is not None:
        assert lv["take_profit"] > lv["entry_zone"][1]
