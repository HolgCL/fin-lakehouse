"""Persist the silver company-year table into the local DuckDB warehouse.

Silver is fully rebuildable from bronze (§3): each run replaces silver.company_year wholesale,
so re-running normalization is always idempotent.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

WAREHOUSE_PATH = Path("data/warehouse.duckdb")


def write_company_year(df: pl.DataFrame, warehouse_path: Path = WAREHOUSE_PATH) -> None:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse_path))
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS silver")
        con.register("company_year_arrow", df.to_arrow())
        con.execute(
            "CREATE OR REPLACE TABLE silver.company_year AS SELECT * FROM company_year_arrow"
        )
        con.unregister("company_year_arrow")
    finally:
        con.close()
