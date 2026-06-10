"""Technical / momentum entry & exit signals from daily OHLCV.

Long-only, trend-following: 50/200-MA structure + crossovers, RSI(14), 52-week
breakout/pullback positioning, and an ATR(14) trailing stop. Produces a single
action per stock — BUY / HOLD / TRIM / EXIT / AVOID — plus concrete price levels.

This is a mechanical rule set for research/education, not investment advice.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app import config


def _rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()


def _recent_cross(fast: pd.Series, slow: pd.Series, lookback: int) -> tuple[bool, bool]:
    """(golden, death) — did fast cross above/below slow within `lookback` bars?"""
    d = (fast - slow).dropna()
    if len(d) < 2:
        return (False, False)
    signs = np.sign(d.tail(lookback + 1).values)
    golden = any(signs[i] <= 0 and signs[i + 1] > 0 for i in range(len(signs) - 1))
    death = any(signs[i] >= 0 and signs[i + 1] < 0 for i in range(len(signs) - 1))
    return (golden, death)


def compute_signal(df: pd.DataFrame) -> dict:
    if df is None or df.empty or "Close" not in df:
        return {"signal": "NO_DATA"}
    df = df.dropna(subset=["Close"])
    close = df["Close"].astype(float)
    if len(close) < config.SMA_FAST + 5:
        return {"signal": "INSUFFICIENT_HISTORY", "bars": int(len(close))}

    price = float(close.iloc[-1])
    sma_fast_s = close.rolling(config.SMA_FAST).mean()
    sma_slow_s = close.rolling(config.SMA_SLOW).mean()
    sma_fast = float(sma_fast_s.iloc[-1]) if not np.isnan(sma_fast_s.iloc[-1]) else None
    has_slow = len(close) >= config.SMA_SLOW and not np.isnan(sma_slow_s.iloc[-1])
    sma_slow = float(sma_slow_s.iloc[-1]) if has_slow else None

    rsi_s = _rsi(close, config.RSI_PERIOD)
    rsi = float(rsi_s.iloc[-1]) if not np.isnan(rsi_s.iloc[-1]) else None
    atr_s = _atr(df, config.ATR_PERIOD)
    atr = float(atr_s.iloc[-1]) if not np.isnan(atr_s.iloc[-1]) else None

    high_52w = float(close.tail(252).max())
    low_52w = float(close.tail(252).min())

    golden, death = (_recent_cross(sma_fast_s, sma_slow_s, config.CROSS_LOOKBACK)
                     if has_slow else (False, False))

    # structural trend
    uptrend = bool(sma_slow and price > sma_slow and sma_fast and sma_fast > sma_slow)
    downtrend = bool(sma_slow and price < sma_slow and sma_fast and sma_fast < sma_slow)

    near_high = price >= high_52w * (1 - config.BREAKOUT_NEAR_HIGH_PCT)
    near_fast = sma_fast is not None and abs(price / sma_fast - 1) <= config.PULLBACK_NEAR_FAST_PCT
    extended = sma_fast is not None and price > sma_fast * (1 + config.EXTENDED_ABOVE_FAST_PCT)
    overbought = rsi is not None and rsi >= config.RSI_OVERBOUGHT
    oversold = rsi is not None and rsi <= config.RSI_OVERSOLD

    trailing_stop = round(price - config.ATR_STOP_MULT * atr, 2) if atr else None
    risk = (price - trailing_stop) if trailing_stop else None
    take_profit = round(price + config.REWARD_RISK * risk, 2) if risk and risk > 0 else None

    reasons: list[str] = []

    # ----- decision (exit checks first, then trim, then entry) -----
    if death:
        signal = "EXIT"; reasons.append("death cross (50-MA below 200-MA)")
    elif sma_slow and price < sma_slow:
        signal = "EXIT"; reasons.append("price below 200-MA (trend lost)")
    elif sma_fast and price < sma_fast and downtrend:
        signal = "EXIT"; reasons.append("below 50-MA in a downtrend")
    elif overbought or extended:
        signal = "TRIM"
        if overbought:
            reasons.append(f"RSI {rsi:.0f} overbought")
        if extended:
            reasons.append(">20% above 50-MA (extended)")
    elif uptrend and not overbought and (golden or near_fast or near_high or oversold):
        signal = "BUY"
        if golden:
            reasons.append("recent golden cross")
        if near_fast:
            reasons.append("pullback to 50-MA")
        if near_high:
            reasons.append("breakout near 52w high")
        if oversold:
            reasons.append(f"RSI {rsi:.0f} oversold bounce")
    elif uptrend:
        signal = "HOLD"; reasons.append("intact uptrend, no fresh trigger")
    else:
        signal = "AVOID"; reasons.append("no confirmed uptrend")

    # entry zone: from the 50-MA support up to current price (scale in within)
    entry_low = round(min(price, sma_fast), 2) if sma_fast else None
    entry_high = round(price, 2)

    return {
        "signal": signal,
        "reasons": reasons,
        "indicators": {
            "price": round(price, 2),
            "sma50": round(sma_fast, 2) if sma_fast else None,
            "sma200": round(sma_slow, 2) if sma_slow else None,
            "rsi14": round(rsi, 1) if rsi is not None else None,
            "atr14": round(atr, 2) if atr else None,
            "trend": "up" if uptrend else "down" if downtrend else "neutral",
            "golden_cross": golden,
            "death_cross": death,
            "dist_52w_high": round(price / high_52w - 1, 4) if high_52w else None,
        },
        "levels": {
            "entry_zone": [entry_low, entry_high] if entry_low else None,
            "stop_loss": trailing_stop,
            "take_profit": take_profit,
            "support_50ma": round(sma_fast, 2) if sma_fast else None,
            "resistance_52w_high": round(high_52w, 2),
            "support_52w_low": round(low_52w, 2),
        },
    }
