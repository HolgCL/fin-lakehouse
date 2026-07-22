"""End-to-end silver build: every landed bronze snapshot -> one silver.company_year table.

Runs via `make build`. Silver is fully rebuildable from bronze (§3): every run discovers all
landed companies fresh from data/bronze/cik=*/ and replaces the whole table -- no incremental
or upsert logic needed. entityName is read directly from each snapshot's own JSON, not
hardcoded per company, so this scales to the full universe (universe.py) with no per-company
wiring.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import structlog

from fin_lakehouse.silver.load import WAREHOUSE_PATH, write_company_year
from fin_lakehouse.silver.normalize import extract_company_year

logger = structlog.get_logger()

BRONZE_ROOT = Path("data/bronze")


def _latest_snapshot(cik_dir: Path) -> Path:
    snapshots = sorted(cik_dir.glob("landed=*/companyfacts.json"))
    if not snapshots:
        raise FileNotFoundError(f"no companyfacts.json snapshot under {cik_dir}")
    return snapshots[-1]


def build_silver(
    bronze_root: Path = BRONZE_ROOT, warehouse_path: Path = WAREHOUSE_PATH
) -> pl.DataFrame:
    cik_dirs = sorted(bronze_root.glob("cik=*"))
    if not cik_dirs:
        raise FileNotFoundError(f"no bronze data under {bronze_root}; run `make ingest` first")

    frames: list[pl.DataFrame] = []
    for cik_dir in cik_dirs:
        cik10 = cik_dir.name.removeprefix("cik=")
        snapshot_path = _latest_snapshot(cik_dir)
        raw = snapshot_path.read_bytes()
        entity_name = json.loads(raw)["entityName"]
        df = extract_company_year(cik10, entity_name, raw)
        logger.info(
            "silver.company_built",
            cik=cik10,
            entity_name=entity_name,
            rows=df.height,
            source=str(snapshot_path),
        )
        frames.append(df)

    combined = pl.concat(frames, how="vertical")
    write_company_year(combined, warehouse_path=warehouse_path)
    logger.info("silver.built", companies=len(frames), rows=combined.height)
    return combined


def main() -> None:
    build_silver()


if __name__ == "__main__":
    main()
