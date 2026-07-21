"""Bronze layer: land raw EDGAR companyfacts JSON verbatim, partitioned by cik + landed date.

Raw is sacred (§3): bytes are written exactly as received from EDGAR, never parsed and
re-serialized. Partitioning by ingestion date keeps bronze append-only across ingestion
runs — re-running on the same day is idempotent, re-running later preserves prior snapshots.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

BRONZE_ROOT = Path("data/bronze")


def land_company_facts(
    cik10: str,
    payload: bytes,
    landed_on: dt.date | None = None,
    bronze_root: Path = BRONZE_ROOT,
) -> Path:
    """Write a companyfacts payload to data/bronze/cik={cik10}/landed={date}/companyfacts.json."""
    landed_on = landed_on or dt.date.today()
    partition = bronze_root / f"cik={cik10}" / f"landed={landed_on.isoformat()}"
    partition.mkdir(parents=True, exist_ok=True)
    out_path = partition / "companyfacts.json"
    out_path.write_bytes(payload)
    return out_path
