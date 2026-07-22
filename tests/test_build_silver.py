"""build_silver multi-company tests -- regression coverage for the Null-vs-Float64 dtype bug
found at milestone 5 scale-out: a company with an entirely-null field (e.g. short_term_debt
missing for every fiscal year) made polars infer that column as Null instead of Float64, which
then failed to concatenate with other companies that do have data for it (AGENTS.md milestone 5
log). extract_company_year's explicit schema (silver/normalize.py) is what fixes this; this test
exercises it through the actual multi-company concat path in build_silver.
"""

import datetime as dt
import json
from pathlib import Path
from typing import Any

import duckdb

from fin_lakehouse.build_silver import build_silver

FIXTURE = Path(__file__).parent / "fixtures" / "khc_companyfacts.json"


def _fact(fy: int, end: str, filed: str, val: float) -> dict[str, Any]:
    return {
        "end": end,
        "val": val,
        "accn": "0",
        "fy": fy,
        "fp": "FY",
        "form": "10-K",
        "filed": filed,
    }


def _land(bronze_root: Path, cik10: str, payload: dict[str, Any]) -> None:
    partition = bronze_root / f"cik={cik10}" / f"landed={dt.date.today().isoformat()}"
    partition.mkdir(parents=True)
    (partition / "companyfacts.json").write_bytes(json.dumps(payload).encode())


def test_build_silver_concatenates_companies_with_different_null_fields(tmp_path: Path) -> None:
    bronze_root = tmp_path / "bronze"
    warehouse_path = tmp_path / "warehouse.duckdb"

    # Company A has Assets data but never reports ShortTermBorrowings at all.
    company_a = {
        "entityName": "Company A",
        "facts": {
            "us-gaap": {
                "Assets": {"units": {"USD": [_fact(2020, "2020-12-31", "2021-02-01", 100.0)]}},
            }
        },
    }
    # Company B has both Assets and ShortTermBorrowings.
    company_b = {
        "entityName": "Company B",
        "facts": {
            "us-gaap": {
                "Assets": {"units": {"USD": [_fact(2020, "2020-12-31", "2021-02-01", 200.0)]}},
                "ShortTermBorrowings": {
                    "units": {"USD": [_fact(2020, "2020-12-31", "2021-02-01", 5.0)]}
                },
            }
        },
    }
    _land(bronze_root, "0000000001", company_a)
    _land(bronze_root, "0000000002", company_b)

    combined = build_silver(bronze_root=bronze_root, warehouse_path=warehouse_path)

    assert combined.height == 2
    assert set(combined["entity_name"]) == {"Company A", "Company B"}

    con = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT entity_name, short_term_debt FROM silver.company_year ORDER BY entity_name"
        ).fetchall()
    finally:
        con.close()
    assert rows == [("Company A", None), ("Company B", 5.0)]


def test_build_silver_uses_latest_snapshot_and_reads_entity_name_from_json(tmp_path: Path) -> None:
    bronze_root = tmp_path / "bronze"
    warehouse_path = tmp_path / "warehouse.duckdb"
    raw = json.loads(FIXTURE.read_text())
    _land(bronze_root, "0001637459", raw)

    combined = build_silver(bronze_root=bronze_root, warehouse_path=warehouse_path)

    assert combined.height >= 1
    assert combined["entity_name"][0] == "Kraft Heinz Co"
