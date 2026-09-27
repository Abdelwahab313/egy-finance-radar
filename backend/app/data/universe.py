"""Curated EGX universe: liquid, large and mid-cap names, mostly EGX30 constituents.

Curated instead of scanning all ~280 EGX tickers: yfinance is flaky on thin
names, and a small account should only touch liquid stocks anyway.

`fundamentals` are STATIC fallbacks from hand research. They are directional
only and are used when a live fundamentals fetch is unavailable. Live
price-derived metrics (beta, volatility, returns, avg traded value) override.
Keyed by the plain symbol; Yahoo ticker = symbol + ".CA".

PROVENANCE RULE. A `fundamentals` key is written only when the value was
verified. An ABSENT key means NOT FOUND: never a zero, never an estimate, never
a figure carried over from a sibling name. `classifier._g()` defaults a missing
field, a name with no `market_cap` and no live fetch classifies as
`speculative`, and `passes_gates()` fails it on `no_live_data`. An unpriceable
name being excluded is the correct outcome. Where two sources disagree past
MARK_CONFLICT_PCT (screening rule 4), write NO value for the contested field.

Three kinds of entry live here:
  1. Listed EGX equities.
  2. Fund wrappers (MTF, CI30, CMS, BMM, BRE): invisible to yfinance, priced
     only via config.MANUAL_NAV. Carried for name/sector metadata; they fail
     the live-data gate and are excluded from the shortlist by design.
  3. Screened-and-rejected names, kept so a later pass does not redo research.

Membership is maintained by the `stock-investigator` agent, not by hand.
"""

from __future__ import annotations

# symbol -> static profile
EGX_UNIVERSE: dict[str, dict] = {
    "COMI": {
        "name": "Commercial International Bank",
        "sector": "Banking",
        "fundamentals": {
            "market_cap": 483700000000.0,
            "pe": 7.2,
            "pb": 1.8,
            "dividend_yield": 0.043,
            "payout_ratio": 0.31,
            "roe": 0.26,
            "eps_growth_3y": 0.22,
            "beta": 0.9,
        },
    },
    "ETEL": {
        "name": "Telecom Egypt",
        "sector": "Telecom",
        "fundamentals": {
            "market_cap": 150000000000.0,
            "pe": 6.0,
            "pb": 1.1,
            "dividend_yield": 0.055,
            "payout_ratio": 0.4,
            "roe": 0.19,
            "eps_growth_3y": 0.18,
            "beta": 0.75,
        },
    },
    "EAST": {
        "name": "Eastern Company (Tobacco)",
        "sector": "Tobacco",
        "fundamentals": {
            "pe": 11.56,
            "pb": 3.0,
            "beta": 0.8,
        },
    },
    "ABUK": {
        "name": "Abu Qir Fertilizers",
        "sector": "Chemicals & Fertilizers",
        "fundamentals": {
            "market_cap": 90000000000.0,
            "pe": 7.0,
            "pb": 2.2,
            "dividend_yield": 0.029,
            "payout_ratio": 0.76,
            "roe": 0.32,
            "eps_growth_3y": 0.4,
            "beta": 0.95,
        },
    },
    "MFPC": {
        "name": "Misr Fertilizers Production (MOPCO)",
        "sector": "Chemicals & Fertilizers",
        "fundamentals": {
            "market_cap": 90000000000.0,
            "pe": 6.8,
            "pb": 2.0,
            "dividend_yield": 0.08,
            "payout_ratio": 0.85,
            "roe": 0.28,
            "eps_growth_3y": 0.08,
            "beta": 1.0,
        },
    },
    "SWDY": {
        "name": "El Sewedy Electric",
        "sector": "Industrials",
        "fundamentals": {
            "market_cap": 165800000000.0,
            "pe": 16.85,
            "pb": 2.4,
            "dividend_yield": 0.021,
            "beta": 1.1,
        },
    },
    "HRHO": {
        "name": "EFG Holding (Hermes)",
        "sector": "Financial Services",
        "fundamentals": {
            "market_cap": 39500000000.0,
            "pe": 8.0,
            "pb": 1.0,
            "dividend_yield": 0.011,
            "payout_ratio": 0.1,
            "roe": 0.17,
            "eps_growth_3y": 0.2,
            "beta": 1.25,
        },
    },
    "TMGH": {
        "name": "Talaat Moustafa Group",
        "sector": "Real Estate",
        "fundamentals": {
            "market_cap": 197800000000.0,
            "pe": 13.9,
            "pb": 1.6,
            "dividend_yield": 0.003,
            "payout_ratio": 0.04,
            "roe": 0.16,
            "eps_growth_3y": 0.28,
            "beta": 1.05,
        },
    },
    "EMFD": {
        "name": "Emaar Misr for Development",
        "sector": "Real Estate",
        "fundamentals": {
            "market_cap": 63000000000.0,
            "pe": 6.7,
            "pb": 1.4,
            "dividend_yield": 0.0,
            "payout_ratio": 0.0,
            "roe": 0.18,
            "eps_growth_3y": 0.3,
            "beta": 1.15,
        },
    },
    "FWRY": {
        "name": "Fawry for Banking Technology",
        "sector": "Fintech",
        "fundamentals": {
            "market_cap": 67600000000.0,
            "pe": 20.7,
            "pb": 4.5,
            "dividend_yield": 0.0,
            "payout_ratio": 0.0,
            "roe": 0.22,
            "eps_growth_3y": 0.45,
            "beta": 1.3,
        },
    },
    "JUFO": {
        "name": "Juhayna Food Industries",
        "sector": "Consumer Staples",
        "fundamentals": {
            "market_cap": 30000000000.0,
            "pe": 17.96,
            "pb": 2.2,
            "dividend_yield": 0.0071,
            "payout_ratio": 0.4,
            "roe": 0.2,
            "beta": 0.85,
        },
    },
    "ADIB": {
        "name": "Abu Dhabi Islamic Bank - Egypt",
        "sector": "Banking",
        "fundamentals": {
            "market_cap": 78080000000.0,
            "pe": 5.45,
            "pb": 1.79,
            "roe": 0.3879,
            "eps_growth_3y": 0.24,
            "beta": 0.95,
        },
    },
    "EGAL": {
        "name": "Egypt Aluminum",
        "sector": "Metals & Mining",
        "fundamentals": {
            "market_cap": 130000000000.0,
            "pe": 8.0,
            "pb": 2.0,
            "dividend_yield": 0.04,
            "payout_ratio": 0.5,
            "roe": 0.21,
            "eps_growth_3y": 0.1,
            "beta": 1.1,
        },
    },
    "CIRA": {
        "name": "Cairo Investment & Real Estate (Education)",
        "sector": "Education",
        "fundamentals": {
            "market_cap": 20000000000.0,
            "pe": 16.0,
            "pb": 3.0,
            "dividend_yield": 0.01,
            "payout_ratio": 0.2,
            "roe": 0.18,
            "eps_growth_3y": 0.22,
            "beta": 0.9,
        },
    },
    "ISPH": {
        "name": "Ibnsina Pharma",
        "sector": "Healthcare Distribution",
        "fundamentals": {
            "market_cap": 12000000000.0,
            "pe": 12.0,
            "pb": 2.5,
            "dividend_yield": 0.02,
            "payout_ratio": 0.3,
            "roe": 0.19,
            "eps_growth_3y": 0.2,
            "beta": 1.05,
        },
    },
    "MBSC": {
        "name": "Misr Beni Suef Cement",
        "sector": "Construction & Building Materials",
        "fundamentals": {
            "market_cap": 14490000000.0,
            "pe": 4.42,
            "pb": 2.81,
            "dividend_yield": 0.073,
            "payout_ratio": 0.32,
            "roe": 0.45,
            "eps_growth_3y": 0.25,
            "beta": 0.55,
        },
    },
    # USD-quoted line (ex-EKHO, renamed 01-Dec-2025); unpriceable in EGP without an FX leg.
    "VLMR": {
        "name": "Valmore Holding for Investment (USD line, ex-EKHO)",
        "sector": "Diversified Holding",
        "fundamentals": {
            "market_cap": 25100000000.0,
            "pe": 6.56,
            "pb": 1.3,
            "dividend_yield": 0.054,
            "payout_ratio": 0.35,
            "roe": 0.2,
            "eps_growth_3y": 0.1,
            "beta": 0.9,
        },
    },
    "VLMRA": {
        "name": "Valmore Holding for Investment (EGP line, ex-EKHOA)",
        "sector": "Diversified Holding",
        "fundamentals": {
            "market_cap": 25100000000.0,
            "pe": 6.56,
            "pb": 1.3,
            "dividend_yield": 0.054,
            "payout_ratio": 0.35,
            "roe": 0.2,
            "eps_growth_3y": 0.1,
            "beta": 0.9,
        },
    },
    "PHAR": {
        "name": "Egyptian International Pharmaceutical Industries (EIPICO)",
        "sector": "Pharmaceuticals",
        "fundamentals": {
            "market_cap": 20000000000.0,
            "pe": 10.0,
            "pb": 2.0,
            "dividend_yield": 0.04,
            "payout_ratio": 0.4,
            "roe": 0.2,
            "eps_growth_3y": 0.2,
            "beta": 1.0,
        },
    },
    "ALCN": {
        "name": "Alexandria Container & Cargo Handling",
        "sector": "Transport & Logistics",
        "fundamentals": {
            "pe": 12.5,
            "dividend_yield": 0.057,
        },
    },
    "EFIH": {
        "name": "e-finance for Digital and Financial Investments",
        "sector": "Fintech",
        "fundamentals": {
            "pe": 33.45,
            "dividend_yield": 0.0119,
        },
    },
    "EFID": {
        "name": "Edita Food Industries",
        "sector": "Consumer Staples",
        "fundamentals": {
            "pe": 13.28,
            "dividend_yield": 0.0264,
        },
    },
    "ORWE": {
        "name": "Oriental Weavers Carpet",
        "sector": "Textiles",
        "fundamentals": {
            "market_cap": 17130000000.0,
            "pe": 8.57,
            "dividend_yield": 0.0582,
        },
    },
    # No pe on purpose: sources disagree past MARK_CONFLICT_PCT; write no value for a contested field.
    "SCEM": {
        "name": "Sinai Cement",
        "sector": "Construction & Building Materials",
        "fundamentals": {
            "dividend_yield": 0.0,
        },
    },
    "CLHO": {
        "name": "Cleopatra Hospital",
        "sector": "Healthcare Services",
        "fundamentals": {
            "pe": 44.76,
        },
    },
    "AALR": {
        "name": "General Co. for Land Reclamation, Development & Reconstruction",
        "sector": "Real Estate",
        "fundamentals": {
            "market_cap": 1980000000.0,
        },
    },
    "EXPA": {
        "name": "Export Development Bank of Egypt",
        "sector": "Banking",
        "fundamentals": {
            "market_cap": 28300000000.0,
            "pe": 4.71,
        },
    },
    "AMOC": {
        "name": "Alexandria Mineral Oils Company",
        "sector": "Energy",
        "fundamentals": {},
    },
    "ARCC": {
        "name": "Arabian Cement Company",
        "sector": "Construction & Building Materials",
        "fundamentals": {},
    },
    "BTFH": {
        "name": "Beltone Holding",
        "sector": "Financial Services",
        "fundamentals": {},
    },
    "EGCH": {
        "name": "Egyptian Chemical Industries (Kima)",
        "sector": "Chemicals & Fertilizers",
        "fundamentals": {},
    },
    "GBCO": {
        "name": "GB Corp",
        "sector": "Automotive",
        "fundamentals": {},
    },
    "HELI": {
        "name": "Heliopolis Housing & Development",
        "sector": "Real Estate",
        "fundamentals": {},
    },
    "MCQE": {
        "name": "Misr Cement (Qena)",
        "sector": "Construction & Building Materials",
        "fundamentals": {},
    },
    "ORHD": {
        "name": "Orascom Development Egypt",
        "sector": "Real Estate",
        "fundamentals": {},
    },
    "OIH": {
        "name": "Orascom Investment Holding",
        "sector": "Diversified Holding",
        "fundamentals": {},
    },
    "PHDC": {
        "name": "Palm Hills Development",
        "sector": "Real Estate",
        "fundamentals": {},
    },
    "CCAP": {
        "name": "Qalaa Holdings",
        "sector": "Diversified Holding",
        "fundamentals": {},
    },
    "RAYA": {
        "name": "Raya Holding for Financial Investments",
        "sector": "Diversified Holding",
        "fundamentals": {},
    },
    "RMDA": {
        "name": "Rameda (Tenth of Ramadan Pharmaceutical)",
        "sector": "Pharmaceuticals",
        "fundamentals": {},
    },
    # EGX line returns bars from yfinance but zero traded value for weeks at a time; treat the feed as frozen and confirm on a second source (screening rule 5).
    "ORAS": {
        "name": "Orascom Construction PLC",
        "sector": "Construction & Engineering",
        "fundamentals": {},
    },

    # --- Fund wrappers (priced via config.MANUAL_NAV) ---
    "MTF": {
        "name": "Misr Insurance Takaful money-market fund",
        "sector": "Money market fund",
        "fundamentals": {},
    },
    "CI30": {
        "name": "Misr Equity Fund (tracks EGX30 Capped, 15% per-name ceiling)",
        "sector": "Broad EGX equity",
        "fundamentals": {},
    },
    "CMS": {
        "name": "Misr Sharia Equity Fund (tracks EGX33 Shariah)",
        "sector": "Broad EGX equity",
        "fundamentals": {},
    },
    "BMM": {
        "name": "Beltone Meya Meya (tracks EGX100 equal-weighted)",
        "sector": "Broad EGX equity",
        "fundamentals": {},
    },
    "BRE": {
        "name": "Beltone Real Estate (sector fund, 10% performance fee)",
        "sector": "Real Estate",
        "fundamentals": {},
    },
}


def yahoo_ticker(symbol: str) -> str:
    from app.config import YF_SUFFIX
    return f"{symbol}{YF_SUFFIX}"


def symbols() -> list[str]:
    return list(EGX_UNIVERSE.keys())
