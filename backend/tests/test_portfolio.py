"""Invariants for the portfolio builder + fundamentals validation.

Run:  pip install pytest && pytest -q
"""

from app import config
from app.analysis.metrics import merge_fundamentals, _live_ok
from app.portfolio.account import _allocate_slots, build_portfolio


def _stock(symbol, bucket, sector, score, price):
    return {"symbol": symbol, "name": symbol, "sector": sector,
            "bucket": bucket, "score": score, "metrics": {"price": price}}


def test_allocate_slots_represents_every_bucket():
    avail = {"stable_bluechip": 3, "value": 3, "growth": 3}
    slots = _allocate_slots(avail, config.TARGET_BUCKET_WEIGHTS, 5)
    assert sum(slots.values()) == 5
    assert all(slots[b] >= 1 for b in avail)          # no bucket dropped
    assert slots["stable_bluechip"] >= slots["growth"]  # weight-ordered


def test_allocate_slots_respects_capacity():
    avail = {"stable_bluechip": 1, "value": 1, "growth": 1}
    slots = _allocate_slots(avail, config.TARGET_BUCKET_WEIGHTS, 5)
    assert sum(slots.values()) == 3                    # capped by availability
    assert all(slots[b] <= avail[b] for b in avail)


def test_portfolio_caps_and_balance():
    shortlist = [
        _stock("COMI", "stable_bluechip", "Banking", 81, 130),
        _stock("MFPC", "stable_bluechip", "Chemicals", 80, 50),
        _stock("ETEL", "stable_bluechip", "Telecom", 77, 95),
        _stock("HRHO", "value", "Financial Services", 80, 26),
        _stock("ADIB", "value", "Banking", 75, 47),
        _stock("EAST", "growth", "Tobacco", 76, 39),
        _stock("FWRY", "growth", "Fintech", 65, 19),
    ]
    pf = build_portfolio(shortlist, capital=10_000)
    assert pf["num_positions"] == config.TARGET_HOLDINGS
    buckets = pf["bucket_exposure"]
    # every target bucket present (the regression we fixed)
    for b in config.TARGET_BUCKET_WEIGHTS:
        assert b in buckets, f"missing bucket {b}"
    # target-weight cap holds (allow tiny integer-share drift on realized weight)
    assert all(p["target_weight"] <= config.MAX_POSITION_PCT + 1e-6
               for p in pf["positions"])
    assert all(p["actual_weight"] <= config.MAX_POSITION_PCT + 0.02
               for p in pf["positions"])
    # never spend more than capital
    assert pf["invested_value"] + pf["entry_costs_total"] <= 10_000 + 1e-6


def test_live_fundamental_validation_rejects_garbage():
    # Yahoo's bogus EGX P/E of 0.12 must be rejected -> static fallback used
    merged = merge_fundamentals(static={"pe": 16.0}, live={"pe": 0.12}, computed={})
    assert merged["pe"] == 16.0
    assert merged["provenance"]["pe"] == "static"
    # a sane live P/E is kept
    merged2 = merge_fundamentals(static={"pe": 16.0}, live={"pe": 8.5}, computed={})
    assert merged2["pe"] == 8.5
    assert merged2["provenance"]["pe"] == "live"
    assert _live_ok("pe", 0.12) is False and _live_ok("pe", 8.5) is True
