from pathlib import Path

import duckdb
import polars as pl

from fin_lakehouse.silver.load import write_company_year


def test_write_company_year_creates_queryable_table(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    df = pl.DataFrame(
        {
            "cik": ["0001637459"],
            "entity_name": ["Kraft Heinz Co"],
            "fiscal_year": [2024],
            "total_assets": [90000.0],
        }
    )
    write_company_year(df, warehouse_path=warehouse)

    con = duckdb.connect(str(warehouse))
    try:
        result = con.execute(
            "SELECT total_assets FROM silver.company_year WHERE fiscal_year = 2024"
        ).fetchone()
    finally:
        con.close()
    assert result is not None
    assert result[0] == 90000.0


def test_write_company_year_is_idempotent_replace(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    df_v1 = pl.DataFrame(
        {"cik": ["X"], "entity_name": ["Test"], "fiscal_year": [2020], "total_assets": [1.0]}
    )
    df_v2 = pl.DataFrame(
        {"cik": ["X"], "entity_name": ["Test"], "fiscal_year": [2021], "total_assets": [2.0]}
    )

    write_company_year(df_v1, warehouse_path=warehouse)
    write_company_year(df_v2, warehouse_path=warehouse)

    con = duckdb.connect(str(warehouse))
    try:
        rows = con.execute("SELECT fiscal_year FROM silver.company_year").fetchall()
    finally:
        con.close()
    assert rows == [(2021,)]  # v1 fully replaced, not appended
