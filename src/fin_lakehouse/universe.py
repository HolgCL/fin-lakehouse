"""The ~20-ticker company universe (docs/PROJECT_BRIEF.md §9 milestone 5), human-confirmed.

Large, well-tagged SEC filers spanning sectors. Deliberately includes several companies with
real, documented historical red flags (GE, T, BA, INTC) alongside healthy blue-chips, so the
detector has real findings to surface rather than a wall of clean results.
"""

from __future__ import annotations

UNIVERSE: list[str] = [
    # Consumer staples
    "KHC",
    "PG",
    "KO",
    "PEP",
    "MDLZ",
    "GIS",
    "CL",
    # Tech
    "AAPL",
    "MSFT",
    "GOOGL",
    "META",
    "ORCL",
    "INTC",
    # Industrials / autos
    "GE",
    "BA",
    "F",
    "GM",
    # Retail
    "WMT",
    "TGT",
    "COST",
    # Telecom / media
    "T",
    "DIS",
]
