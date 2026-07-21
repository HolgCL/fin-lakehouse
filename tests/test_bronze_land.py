"""Bronze landing tests: verbatim bytes, correct partitioning, idempotency."""

import datetime as dt
from pathlib import Path

from fin_lakehouse.bronze.land import land_company_facts

FIXTURE = Path(__file__).parent / "fixtures" / "khc_companyfacts.json"


def test_land_writes_bytes_verbatim(tmp_path: Path) -> None:
    payload = FIXTURE.read_bytes()
    out_path = land_company_facts(
        "0001637459", payload, landed_on=dt.date(2026, 1, 15), bronze_root=tmp_path
    )
    assert out_path.read_bytes() == payload


def test_land_partitions_by_cik_and_landed_date(tmp_path: Path) -> None:
    out_path = land_company_facts(
        "0001637459", b"{}", landed_on=dt.date(2026, 1, 15), bronze_root=tmp_path
    )
    assert out_path == tmp_path / "cik=0001637459" / "landed=2026-01-15" / "companyfacts.json"


def test_land_same_day_rerun_is_idempotent(tmp_path: Path) -> None:
    first = land_company_facts(
        "0001637459", b'{"v": 1}', landed_on=dt.date(2026, 1, 15), bronze_root=tmp_path
    )
    second = land_company_facts(
        "0001637459", b'{"v": 1}', landed_on=dt.date(2026, 1, 15), bronze_root=tmp_path
    )
    assert first == second
    assert first.read_bytes() == b'{"v": 1}'


def test_land_different_day_creates_new_snapshot(tmp_path: Path) -> None:
    day1 = land_company_facts(
        "0001637459", b'{"v": 1}', landed_on=dt.date(2026, 1, 15), bronze_root=tmp_path
    )
    day2 = land_company_facts(
        "0001637459", b'{"v": 2}', landed_on=dt.date(2026, 1, 16), bronze_root=tmp_path
    )
    assert day1 != day2
    assert day1.read_bytes() == b'{"v": 1}'
    assert day2.read_bytes() == b'{"v": 2}'
