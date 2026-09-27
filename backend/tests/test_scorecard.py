"""Pure scoring rules from ADR-0007, on synthetic close series."""

from datetime import date

import pandas as pd

from app.analysis.scorecard import score


def _closes(start: date, values: list[float]) -> pd.Series:
    idx = pd.bdate_range(start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


AS_OF = date(2026, 7, 1)
TODAY = date(2026, 9, 27)


def _reco(action="add", horizon="tactical", target=None, stop=None):
    return {"as_of": AS_OF, "horizon": horizon, "action": action,
            "price_target": target, "stop_loss": stop}


def test_target_hit_is_correct_for_add():
    out = score(_reco(target=110, stop=90), _closes(AS_OF, [100, 104, 111, 95]), TODAY)
    assert out["status"] == "target_hit"
    assert out["resolved_on"] == date(2026, 7, 3)
    assert out["correct"] is True
    assert out["entry_price"] == 100


def test_stop_hit_is_wrong_for_add_and_right_for_sell():
    closes = _closes(AS_OF, [100, 96, 89, 120])
    assert score(_reco("add", target=110, stop=90), closes, TODAY)["correct"] is False
    assert score(_reco("sell", stop=90), closes, TODAY)["correct"] is True


def test_same_day_touch_of_both_counts_as_stop():
    out = score(_reco(target=105, stop=95), _closes(AS_OF, [100, 80]), TODAY)
    assert out["status"] == "stop_hit"


def test_expired_uses_sign_of_return():
    closes = _closes(AS_OF, [100.0] * 20 + [103.0])
    up = score(_reco("hold"), closes, TODAY)
    assert up["status"] == "expired" and up["correct"] is True
    down = score(_reco("trim"), closes, TODAY)
    assert down["correct"] is False
    assert abs(up["return_pct"] - 0.03) < 1e-9


def test_open_while_window_runs():
    out = score(_reco(target=200), _closes(AS_OF, [100, 101]), date(2026, 7, 10))
    assert out["status"] == "open"
    assert out["correct"] is None


def test_no_data_when_series_empty_or_starts_too_late():
    assert score(_reco(), None, TODAY)["status"] == "no_data"
    assert score(_reco(), pd.Series(dtype=float), TODAY)["status"] == "no_data"
    late = _closes(date(2026, 7, 20), [100, 101])
    assert score(_reco(), late, TODAY)["status"] == "no_data"


def test_core_window_is_a_year():
    out = score(_reco(horizon="core"), _closes(AS_OF, [100, 101]), TODAY)
    assert out["window_end"] == date(2027, 7, 1)
    assert out["status"] == "open"
