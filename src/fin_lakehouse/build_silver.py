"""Milestone-2 entrypoint: latest bronze KHC snapshot -> silver.company_year.

Runs via `make build`.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from fin_lakehouse.silver.load import write_company_year
from fin_lakehouse.silver.normalize import extract_company_year

logger = structlog.get_logger()

BRONZE_ROOT = Path("data/bronze")
KHC_CIK10 = "0001637459"
KHC_ENTITY_NAME = "Kraft Heinz Co"


def _latest_snapshot(cik10: str) -> Path:
    snapshots = sorted((BRONZE_ROOT / f"cik={cik10}").glob("landed=*/companyfacts.json"))
    if not snapshots:
        raise FileNotFoundError(f"no bronze snapshot for cik={cik10}; run `make ingest` first")
    return snapshots[-1]


def build_silver(cik10: str, entity_name: str) -> None:
    snapshot_path = _latest_snapshot(cik10)
    raw = snapshot_path.read_bytes()
    df = extract_company_year(cik10, entity_name, raw)
    write_company_year(df)
    logger.info("silver.built", cik=cik10, rows=df.height, source=str(snapshot_path))


def main() -> None:
    build_silver(KHC_CIK10, KHC_ENTITY_NAME)


if __name__ == "__main__":
    main()
