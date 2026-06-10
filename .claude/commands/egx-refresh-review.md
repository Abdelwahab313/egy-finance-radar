---
description: Refresh EGX live data and re-run the adversarial critique of the pipeline
argument-hint: "[capital_egp]"
allowed-tools: Bash, Read, Edit, Agent
---

You are refreshing the **EGY Finance** EGX pipeline with live data and then critically
reviewing the result. Be adversarial — the goal is to catch regressions and stale/garbage
data, not to reassure. Project root: the repository working directory; backend is in `backend/`.

`$ARGUMENTS` (optional) = a new starting capital in EGP. If provided and numeric, update
`STARTING_CAPITAL_EGP` in `backend/app/config.py` to that value before refreshing; otherwise
leave the config untouched.

## Steps

1. **(Optional) Set capital.** If `$ARGUMENTS` is a number, Edit `backend/app/config.py` so
   `STARTING_CAPITAL_EGP` matches it. Report the old → new value.

2. **Refresh live data.** From `backend/`, activate the venv and run the collector. It needs
   network access (yfinance) — if the sandbox blocks it, the call will return empty fetches, so
   run it with the sandbox disabled:
   ```bash
   cd backend && source .venv/bin/activate && python -m app.agent.collector
   ```
   Note how many symbols returned live prices and which `index_source` was used for beta.

3. **Run the tests** to confirm no invariants broke:
   ```bash
   cd backend && source .venv/bin/activate && pytest -q
   ```

4. **Load the fresh snapshot** (`backend/data/snapshot.json`) and present:
   - The portfolio: holdings, shares, weights, bucket & sector exposures, invested/cash, costs.
   - The entry/exit signals per holding (signal, stop-loss, take-profit, reasons).

5. **Critique it adversarially.** Check each of these and report findings as a table
   (issue · severity · evidence). Do NOT hand-wave — cite concrete numbers from the snapshot:
   - **Data freshness/quality:** read `data_quality`. How many fields are live vs static? Is
     `beta_source` the proxy or real EGX30? Did any live P/E / P/B look implausible (and was it
     correctly rejected to static)? Is `generated_at` recent?
   - **Stale or absurd values:** any price unchanged across refreshes, P/E ≤ 1.5 or ≥ 150 that
     slipped through, dividend yields or betas that look wrong, 52-week ranges that don't bracket
     the current price.
   - **Portfolio invariants:** every target bucket represented? Max single name ≤ 25% (target) and
     sector ≤ 40%? Bucket weights near the 40/35/25 target? Total invested + costs ≤ capital?
     Cash buffer ~10%? Were any positions dropped because of missing prices?
   - **Classification vs signals disagreement:** list holdings the classifier funded but the
     signal engine flags EXIT or TRIM — call these out explicitly as the actionable tension.
   - **Signal sanity:** stops below entry, targets above entry, trend label consistent with
     price vs 200-MA, RSI in 0–100.

6. **Fix or flag.** For any High/Medium issue with an obvious, low-risk fix, apply it (Edit) and
   re-run steps 2–3 to confirm. For anything ambiguous or design-level, list it as a
   recommendation and ask before changing.

End with a concise verdict: what's healthy, what regressed, and the single highest-value next fix.
