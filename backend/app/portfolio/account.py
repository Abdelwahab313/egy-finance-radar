"""Paper account + balanced value+growth portfolio builder for a small EGP account.

Builds from the curated shortlist, respecting bucket target weights, per-name and
per-sector caps, a cash buffer, and a realistic per-trade cost model.
"""

from __future__ import annotations

from app import config


def sector_group(sector: str) -> str:
    """Collapse economically-equivalent sectors (banks, brokers, fintech ->
    'Financials') so the concentration cap sees one bet, not three."""
    return config.SECTOR_GROUPS.get(sector, sector)


def trade_cost(notional: float) -> float:
    """One-side cost in EGP for a trade of `notional` EGP."""
    broker = config.BROKER[config.ACTIVE_BROKER]
    broker_fee = max(notional * broker["pct"], broker["min_egp"])
    statutory = notional * (config.STAMP_DUTY_PCT + config.EGX_FEE_PCT
                            + config.MCDR_FEE_PCT)
    return broker_fee + statutory


def build_portfolio(shortlist: list[dict], capital: float = config.STARTING_CAPITAL_EGP) -> dict:
    """`shortlist` = list of stock dicts (symbol, bucket, score, metrics.price, sector).

    Returns the constructed portfolio with positions, costs, cash, and diagnostics.
    """
    # Carve the deliberate risk-free T-bill sleeve and the cash buffer off the
    # top; only the rest competes for equities. T-bills ~23% are a real rival to
    # these stocks, so they get a first-class allocation, not leftovers.
    equity_pct = max(0.0, 1.0 - config.CASH_BUFFER_PCT - config.TBILL_SLEEVE_PCT)
    investable = capital * equity_pct
    tbill_amount = capital * config.TBILL_SLEEVE_PCT

    # 1) group eligible candidates by target bucket (best score first)
    by_bucket: dict[str, list[dict]] = {}
    for s in sorted(shortlist, key=lambda x: x.get("score", 0), reverse=True):
        b = s["bucket"]
        if b not in config.TARGET_BUCKET_WEIGHTS:
            continue
        by_bucket.setdefault(b, []).append(s)

    # 2) allocate a NUMBER of holdings per bucket first, so every target bucket
    #    is represented (the old "weight then trim top-N" dropped whole buckets).
    avail = {b: min(len(cs), config.BUCKET_CAPS.get(b, 0)) for b, cs in by_bucket.items()}
    slots = _allocate_slots(avail, config.TARGET_BUCKET_WEIGHTS, config.TARGET_HOLDINGS)

    # 3) within each bucket take the best-scored names and weight by score,
    #    scaling the bucket's names to the bucket's target weight.
    picks: list[dict] = []
    # A bucket can physically hold at most (n_names * MAX_POSITION_PCT); clamp its
    # target to that capacity so a single-name bucket (e.g. `value` after an EXIT
    # block leaves only ADIB) doesn't claim a 35% weight it can't hold and then
    # silently leak the excess into the higher-beta buckets. Unreachable weight
    # renormalizes onto buckets that still have spare room.
    active_weight = {}
    for b, n in slots.items():
        if n <= 0:
            continue
        capacity = n * config.MAX_POSITION_PCT
        active_weight[b] = min(config.TARGET_BUCKET_WEIGHTS[b], capacity)
    wsum = sum(active_weight.values()) or 1.0
    for bucket, n in slots.items():
        if n <= 0:
            continue
        chosen = by_bucket[bucket][:n]
        bucket_w = active_weight[bucket] / wsum          # renormalized across active
        total_score = sum(c.get("score", 0) for c in chosen) or 1.0
        for c in chosen:
            picks.append({**c, "target_weight": bucket_w * c.get("score", 0) / total_score})
    _renormalize(picks)

    # 2) apply per-name and per-sector caps, renormalize
    _apply_caps(picks)

    # 3) convert weights to whole-share positions
    raw = []
    for p in picks:
        price = (p.get("metrics") or {}).get("price")
        if not price or price <= 0:
            continue
        budget = investable * p["target_weight"]
        shares = int(budget // price)
        if shares <= 0:
            continue
        raw.append({"src": p, "price": price, "shares": shares})

    # 3b) re-enforce the per-name and per-sector caps on the ACTUAL whole-share
    # notionals. Integer rounding can push a name or sector just over a cap that
    # held on continuous weights (MFPC 25.0% target -> 25.3% actual; Financials
    # 40.0% -> 40.6%). Trim a share at a time until both caps hold post-rounding.
    _enforce_actual_caps(raw)

    positions = []
    spent = 0.0
    total_cost = 0.0
    for r in raw:
        p, price, shares = r["src"], r["price"], r["shares"]
        if shares <= 0:
            continue
        notional = shares * price
        cost = trade_cost(notional)
        positions.append({
            "symbol": p["symbol"],
            "name": p["name"],
            "sector": p["sector"],
            "bucket": p["bucket"],
            "score": p.get("score"),
            "price": round(price, 2),
            "shares": shares,
            "notional": round(notional, 2),
            "entry_cost": round(cost, 2),
            "target_weight": round(p["target_weight"], 4),
        })
        spent += notional
        total_cost += cost

    invested = spent + total_cost
    for pos in positions:
        pos["actual_weight"] = round(pos["notional"] / spent, 4) if spent else 0.0

    cash_remaining = capital - invested - tbill_amount
    return {
        "starting_capital": round(capital, 2),
        "cash_buffer_pct": config.CASH_BUFFER_PCT,
        "equity_pct": round(equity_pct, 4),
        "broker": config.ACTIVE_BROKER,
        "tbill_sleeve": {
            "amount_egp": round(tbill_amount, 2),
            "pct_of_capital": config.TBILL_SLEEVE_PCT,
            "annual_yield": config.TBILL_ANNUAL_YIELD,
            "expected_annual_income_egp": round(tbill_amount * config.TBILL_ANNUAL_YIELD, 2),
            "note": "Risk-free EGP T-bill anchor; the hurdle every stock must beat.",
        },
        "positions": positions,
        "invested_value": round(spent, 2),
        "entry_costs_total": round(total_cost, 2),
        "cash_remaining": round(cash_remaining, 2),
        "num_positions": len(positions),
        "sector_exposure": _sector_exposure(positions, spent),
        "sector_group_exposure": _sector_group_exposure(positions, spent),
        "bucket_exposure": _bucket_exposure(positions, spent),
        "notes": _notes(positions),
    }


def _allocate_slots(avail: dict[str, int], weights: dict[str, float],
                    total: int) -> dict[str, int]:
    """Distribute `total` holdings across buckets ~proportionally to target weights,
    guaranteeing >=1 slot for every bucket that has a candidate (so a balanced
    value+growth book never silently drops a whole bucket), capped by availability.
    """
    active = [b for b in weights if avail.get(b, 0) > 0 and weights[b] > 0]
    slots = {b: 0 for b in active}
    if not active:
        return slots
    # seed 1 each, richest target weight first, until we run out of total
    for b in sorted(active, key=lambda x: weights[x], reverse=True):
        if sum(slots.values()) >= total:
            break
        slots[b] = 1
    # fill the rest greedily by largest proportional deficit, respecting capacity
    while sum(slots.values()) < total:
        best, best_gap = None, -1.0
        for b in active:
            if slots[b] >= avail[b]:
                continue
            gap = weights[b] - slots[b] / total
            if gap > best_gap:
                best, best_gap = b, gap
        if best is None:        # no capacity left anywhere
            break
        slots[best] += 1
    return slots


def _renormalize(picks: list[dict]) -> None:
    total = sum(p["target_weight"] for p in picks) or 1.0
    for p in picks:
        p["target_weight"] /= total


def _cap_and_redistribute(picks: list[dict], cap: float, key) -> None:
    """Iteratively hold each group's weight <= cap, redistributing the excess to
    uncapped groups proportionally. Converges so caps actually hold after renorm
    (the previous cap-then-renormalize approach let capped names drift back over).

    `key(p)` groups picks (identity for per-name, sector for per-sector).
    """
    if not picks or cap >= 1.0:
        return
    _renormalize(picks)
    for _ in range(50):
        group_w: dict = {}
        for p in picks:
            group_w[key(p)] = group_w.get(key(p), 0.0) + p["target_weight"]
        over = {g: w for g, w in group_w.items() if w > cap + 1e-9}
        if not over:
            return
        # pin over-cap groups to `cap` (scaling members proportionally within group)
        for g in over:
            scale = cap / group_w[g]
            for p in picks:
                if key(p) == g:
                    p["target_weight"] *= scale
        pinned = sum(min(group_w[g], cap) for g in over)
        free_groups = [g for g in group_w if g not in over]
        free_total = sum(group_w[g] for g in free_groups)
        room = max(0.0, 1.0 - pinned)
        if free_total <= 0:
            return
        scale_free = room / free_total
        for p in picks:
            if key(p) in free_groups:
                p["target_weight"] *= scale_free


def _apply_caps(picks: list[dict]) -> None:
    _cap_and_redistribute(picks, config.MAX_POSITION_PCT, key=lambda p: p["symbol"])
    _cap_and_redistribute(picks, config.MAX_SECTOR_PCT, key=lambda p: sector_group(p["sector"]))
    # re-check per-name after the sector pass may have shifted weights
    _cap_and_redistribute(picks, config.MAX_POSITION_PCT, key=lambda p: p["symbol"])


def _cap_breaches(raw: list[dict]) -> tuple[float, float]:
    """Return (worst, total) cap breach in weight terms over the ACTUAL whole-share
    notionals: `worst` = the single largest overage of any name or sector-group cap,
    `total` = the sum of all overages. (0, 0) means every cap holds."""
    spent = sum(r["shares"] * r["price"] for r in raw)
    if spent <= 0:
        return 0.0, 0.0
    worst = total = 0.0
    for r in raw:
        over = r["shares"] * r["price"] / spent - config.MAX_POSITION_PCT
        if over > 0:
            worst = max(worst, over)
            total += over
    grp: dict[str, float] = {}
    for r in raw:
        g = sector_group(r["src"]["sector"])
        grp[g] = grp.get(g, 0.0) + r["shares"] * r["price"]
    for n in grp.values():
        over = n / spent - config.MAX_SECTOR_PCT
        if over > 0:
            worst = max(worst, over)
            total += over
    return worst, total


def _enforce_actual_caps(raw: list[dict]) -> None:
    """Hold per-name and per-sector-group exposure <= cap on the ACTUAL whole-share
    notionals. The continuous-weight caps (`_apply_caps`) can drift back over once
    weights are rounded to whole shares, so trim one share at a time from whichever
    lot most reduces the worst breach. Only trims when it strictly helps and never
    below 1 share, so it cleans up rounding drift but bails gracefully (leaving the
    continuous result) on cap combos that are mutually infeasible."""
    # Only fix rounding-scale drift. A large breach means the cap combo is
    # structurally infeasible (e.g. 3 financial names under a 40% sector cap force
    # the 2 non-financials past their name caps); trimming would just swap one
    # breach for a worse one, so leave the continuous-cap result untouched.
    if _cap_breaches(raw)[0] > 0.03:
        return
    for _ in range(1000):
        worst, total = _cap_breaches(raw)
        if total <= 1e-9:
            return
        # trim the share that most reduces TOTAL breach. Minimizing the *sum* (not
        # just the max) rewards clearing one cap even when a coupled cap ticks up a
        # hair, so MFPC's name breach and the Financials sector breach both resolve
        # instead of stalling at a min-max equilibrium with both marginally over.
        best, best_total = None, total
        for r in raw:
            if r["shares"] <= 1:
                continue
            r["shares"] -= 1
            _, t = _cap_breaches(raw)
            r["shares"] += 1
            if t < best_total - 1e-12:
                best, best_total = r, t
        if best is None:          # no single trim improves -> stop (infeasible)
            return
        best["shares"] -= 1


def _sector_exposure(positions, spent) -> dict:
    out: dict[str, float] = {}
    for p in positions:
        out[p["sector"]] = out.get(p["sector"], 0) + p["notional"]
    return {k: round(v / spent, 4) if spent else 0 for k, v in out.items()}


def _sector_group_exposure(positions, spent) -> dict:
    """Exposure after collapsing equivalent sectors — the number the cap acts on."""
    out: dict[str, float] = {}
    for p in positions:
        g = sector_group(p["sector"])
        out[g] = out.get(g, 0) + p["notional"]
    return {k: round(v / spent, 4) if spent else 0 for k, v in out.items()}


def _bucket_exposure(positions, spent) -> dict:
    out: dict[str, float] = {}
    for p in positions:
        out[p["bucket"]] = out.get(p["bucket"], 0) + p["notional"]
    return {k: round(v / spent, 4) if spent else 0 for k, v in out.items()}


def _notes(positions) -> list[str]:
    notes = []
    if not positions:
        notes.append("No positions could be built — check live prices in the snapshot.")
        return notes
    broker = config.BROKER[config.ACTIVE_BROKER]
    smallest = min(p["notional"] for p in positions)
    if smallest < broker["min_egp"] / 0.005:  # < where the 0.5% min would bite
        notes.append("Some positions are small; on a traditional broker the EGP "
                     "minimum fee would exceed 0.5% — the digital broker model is assumed.")
    notes.append(f"Built {len(positions)} positions with a "
                 f"{int(config.CASH_BUFFER_PCT*100)}% cash buffer.")
    return notes
