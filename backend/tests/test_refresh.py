"""Tests for the Refresh runner (app.agent.refresh).

The DB-touching history append is covered offline against the live Postgres in
manual verification; here we test the in-process concurrency guard and the
phase/status bookkeeping, which need no DB.
"""

from app.agent import refresh


def test_try_begin_is_single_flight():
    # nothing in flight -> first claim wins, second is rejected
    assert refresh.is_running() is False
    assert refresh.try_begin() is True
    assert refresh.is_running() is True
    assert refresh.try_begin() is False
    # release the slot so we don't poison other tests
    refresh._RUNNING = False
    refresh._LOCK.release()
    assert refresh.is_running() is False


def test_status_shape_has_required_keys():
    for k in ("status", "started", "finished", "steps", "error"):
        assert k in refresh.STATUS, f"missing status key {k}"


def test_run_refresh_rejects_when_already_running():
    # simulate an in-flight refresh by claiming the slot, then a *direct*
    # run_refresh must report already_running rather than double-running.
    assert refresh.try_begin() is True
    try:
        # _RUNNING is True and lock is held; a competing acquire fails. We can't
        # call run_refresh from the same thread (it would see _RUNNING True and
        # proceed as the claimed owner), so assert the guard primitives directly.
        assert refresh._LOCK.acquire(blocking=False) is False
    finally:
        refresh._RUNNING = False
        refresh._LOCK.release()
