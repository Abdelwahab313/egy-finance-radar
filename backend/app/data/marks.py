"""Owner-supplied dated price marks — the override of last resort.

Why this exists: on 17-Aug-2026 every vendor (Investing.com, TradingView,
stockanalysis, african-markets) quoted ABUK at 73.71 dated 10-Aug, while the
owner's the broker broker screen showed 79.70. The vendors were not wrong about
10-Aug; they were five sessions behind, and nothing in the pipeline could say so.
A mark is the owner reading a number off the broker and writing it down with a
date and a source, which is the highest-quality EGX price this project can get.

Two distinct failures this module names, because they need different responses:

* **vendor lag** — the mark is NEWER than the vendor's last bar. Normal for EGX.
  The mark is appended as the latest bar and the lag is reported in days.
* **conflict** — the mark and the vendor bar are for the SAME date and disagree
  by more than ``MARK_CONFLICT_PCT``. That is CLAUDE.md screening rule 4
  ("reject any name whose vendor quotes disagree by more than ~10% until
  reconciled against the EGX itself"), enforced in code instead of by eye.

A mark cannot manufacture history. If the vendor returned no series at all, the
mark is recorded as unapplied — marking a *held* position with no live price is
``config.MANUAL_NAV``'s job, not this one.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date

from app import config


@dataclass(frozen=True)
class Mark:
    symbol: str
    price: float
    as_of: date
    source: str
    note: str | None = None

    def age_days(self, today: date | None = None) -> int:
        return ((today or date.today()) - self.as_of).days


def load_marks(path: str = config.MARKS_PATH) -> dict[str, Mark]:
    """Read ``data/marks.json``. A missing file is not an error — it means the
    owner has not pasted anything yet, and the vendor stands unopposed."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        blob = json.load(f)

    out: dict[str, Mark] = {}
    for sym, m in (blob.get("marks") or {}).items():
        try:
            out[sym] = Mark(
                symbol=sym,
                price=float(m["price"]),
                as_of=date.fromisoformat(m["as_of"]),
                source=str(m["source"]),
                note=m.get("note"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            # A malformed mark must never silently become a price.
            print(f"[marks] skipping {sym}: {exc}")
    return out


def relative_gap(a: float, b: float) -> float:
    """Symmetric relative difference, so the order of the two quotes cannot
    flatter one of them."""
    denom = max(abs(a), abs(b))
    return abs(a - b) / denom if denom else 0.0
