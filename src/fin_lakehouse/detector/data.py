"""Loads gold company-year metrics from the DuckDB warehouse for the detector to evaluate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

WAREHOUSE_PATH = Path("data/warehouse.duckdb")

# dbt-duckdb's default schema naming: "{target_schema}_{custom_schema}" -- target is "main"
# (profiles.yml has no custom `schema:`), marts get `+schema: gold` (dbt_project.yml)
# -> "main_gold".
# Hardcoded rather than discovered via information_schema: a stale relation left behind by an
# earlier `+schema:` change (dbt doesn't drop old locations on a schema rename) made a discovery
# query silently pick an orphaned, out-of-date copy in a prior run -- see AGENTS.md milestone 4 log.
GOLD_SCHEMA = "main_gold"
GOLD_TABLE = f"{GOLD_SCHEMA}.fct_company_year_metrics"


def load_company_year_metrics(warehouse_path: Path = WAREHOUSE_PATH) -> list[dict[str, Any]]:
    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        table_exists = con.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = ? AND table_name = 'fct_company_year_metrics'",
            [GOLD_SCHEMA],
        ).fetchone()
        if table_exists is None:
            raise RuntimeError(
                f"{GOLD_TABLE} not found; run `make ingest && make build` first"
            )
        columns = [row[0] for row in con.execute(f"DESCRIBE {GOLD_TABLE}").fetchall()]
        rows = con.execute(f"SELECT * FROM {GOLD_TABLE} ORDER BY cik, fiscal_year").fetchall()
    finally:
        con.close()
    return [dict(zip(columns, row, strict=True)) for row in rows]
