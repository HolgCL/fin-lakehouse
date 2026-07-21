"""silver.normalize tests.

Dedup-rule tests use small hand-built synthetic companyfacts payloads so the expected
outcome is obvious from the test data itself, independent of extract_company_year's logic.
The end-to-end test re-derives expected values from the real fixture JSON by a second,
independently hand-written dedup pass (not by calling any function under test), per
AGENTS.md's oracle-independence rule.
"""

import json
from pathlib import Path
from typing import Any

import polars as pl
from structlog.testing import capture_logs

from fin_lakehouse.silver.normalize import extract_company_year

FIXTURE = Path(__file__).parent / "fixtures" / "khc_companyfacts.json"


def _payload(us_gaap: dict[str, Any]) -> bytes:
    return json.dumps({"facts": {"us-gaap": us_gaap}}).encode()


def _fact(
    fy: int, end: str, filed: str, val: float, accn: str = "0000000000-00-000000"
) -> dict[str, Any]:
    return {
        "end": end,
        "val": val,
        "accn": accn,
        "fy": fy,
        "fp": "FY",
        "form": "10-K",
        "filed": filed,
    }


def _duration_fact(
    fy: int, start: str, end: str, filed: str, val: float, accn: str = "0000000000-00-000000"
) -> dict[str, Any]:
    return {**_fact(fy, end, filed, val, accn), "start": start}


def test_dedup_picks_latest_end_over_prior_year_comparative() -> None:
    """Same filing reports both the FY2019 balance and the FY2018 comparative under fy=2019."""
    payload = _payload(
        {
            "Assets": {
                "units": {
                    "USD": [
                        # prior-year comparative shown inside the FY2019 10-K:
                        _fact(fy=2019, end="2018-12-29", filed="2020-02-14", val=999.0),
                        # the actual FY2019 period-end balance:
                        _fact(fy=2019, end="2019-12-28", filed="2020-02-14", val=101450.0),
                    ]
                }
            }
        }
    )
    df = extract_company_year("0000000001", "Test Co", payload)
    row = df.filter(pl.col("fiscal_year") == 2019).to_dicts()[0]
    assert row["total_assets"] == 101450.0


def test_dedup_picks_latest_filed_on_end_date_tie() -> None:
    """A restated value, refiled later for the same period-end, should win."""
    payload = _payload(
        {
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        _fact(fy=2020, end="2020-12-26", filed="2021-02-10", val=2000.0),
                        _fact(fy=2020, end="2020-12-26", filed="2021-06-01", val=1950.0),  # newer
                    ]
                }
            }
        }
    )
    df = extract_company_year("0000000001", "Test Co", payload)
    row = df.filter(pl.col("fiscal_year") == 2020).to_dicts()[0]
    assert row["net_income"] == 1950.0


def test_dedup_excludes_q4_only_duration_fact_sharing_annual_end_date() -> None:
    """Regression: a single 10-K tags both the full year and Q4-only under the same `end`."""
    annual = _duration_fact(2016, "2016-01-04", "2016-12-31", "2017-02-23", 26487000000.0)
    q4_only = _duration_fact(2016, "2016-10-03", "2016-12-31", "2017-02-23", 6857000000.0)
    payload = _payload({"SalesRevenueGoodsNet": {"units": {"USD": [annual, q4_only]}}})

    with capture_logs() as logs:
        df = extract_company_year("0000000001", "Test Co", payload)

    row = df.filter(pl.col("fiscal_year") == 2016).to_dicts()[0]
    assert row["revenue"] == 26487000000.0
    assert not [e for e in logs if e.get("event") == "silver.fact_conflict"]


def test_dedup_prefers_duration_fact_over_instant_tagged_tie() -> None:
    """Regression: a concept normally reported as duration also has a stray instant-tagged fact."""
    duration = _duration_fact(2018, "2017-12-31", "2018-12-29", "2019-06-07", 7008000000.0)
    instant = _fact(fy=2018, end="2018-12-29", filed="2019-06-07", val=6900000000.0)  # no `start`
    payload = _payload({"GoodwillImpairmentLoss": {"units": {"USD": [duration, instant]}}})

    with capture_logs() as logs:
        df = extract_company_year("0000000001", "Test Co", payload)

    row = df.filter(pl.col("fiscal_year") == 2018).to_dicts()[0]
    assert row["goodwill_impairment"] == 7008000000.0
    assert not [e for e in logs if e.get("event") == "silver.fact_conflict"]


def test_conflicting_values_at_same_end_and_filed_logs_warning() -> None:
    payload = _payload(
        {
            "Goodwill": {
                "units": {
                    "USD": [
                        _fact(fy=2021, end="2021-12-25", filed="2022-02-01", val=100.0, accn="A"),
                        _fact(fy=2021, end="2021-12-25", filed="2022-02-01", val=200.0, accn="B"),
                    ]
                }
            }
        }
    )
    with capture_logs() as logs:
        extract_company_year("0000000001", "Test Co", payload)
    conflicts = [e for e in logs if e.get("event") == "silver.fact_conflict"]
    assert len(conflicts) == 1
    assert conflicts[0]["tag"] == "Goodwill"
    assert conflicts[0]["fiscal_year"] == 2021


def test_no_facts_at_all_yields_empty_table() -> None:
    payload = _payload({})  # no concepts anywhere -> no fiscal years are even discoverable
    df = extract_company_year("0000000001", "Test Co", payload)
    assert df.height == 0


def test_missing_field_among_present_years_is_null_and_logged() -> None:
    fact = _fact(fy=2022, end="2022-12-31", filed="2023-02-01", val=1.0)
    payload = _payload(
        {"Assets": {"units": {"USD": [fact]}}}
        # net_income has no data at all for this fy -> should be null, logged
    )
    with capture_logs() as logs:
        df = extract_company_year("0000000001", "Test Co", payload)
    row = df.filter(pl.col("fiscal_year") == 2022).to_dicts()[0]
    assert row["net_income"] is None
    missing = [
        e
        for e in logs
        if e.get("event") == "silver.missing_field" and e.get("field") == "net_income"
    ]
    assert len(missing) == 1


def _oracle_pick(raw_us_gaap: dict[str, Any], tag: str, unit: str, fy: int) -> float:
    """Independent re-implementation of the dedup rule, operating directly on raw JSON."""
    entries = raw_us_gaap[tag]["units"][unit]
    candidates = [e for e in entries if e["form"] == "10-K" and e["fp"] == "FY" and e["fy"] == fy]
    max_end = max(e["end"] for e in candidates)
    candidates = [e for e in candidates if e["end"] == max_end]
    max_filed = max(e["filed"] for e in candidates)
    candidates = [e for e in candidates if e["filed"] == max_filed]
    vals = {c["val"] for c in candidates}
    assert len(vals) == 1, f"conflicting values for {tag} fy={fy}: {vals}"
    return float(candidates[0]["val"])


def test_end_to_end_extraction_matches_independent_oracle_on_real_fixture() -> None:
    raw = json.loads(FIXTURE.read_text())
    us_gaap = raw["facts"]["us-gaap"]

    df = extract_company_year(raw["cik"], raw["entityName"], FIXTURE.read_bytes())
    row = df.filter(pl.col("fiscal_year") == 2024).to_dicts()[0]

    assert row["total_assets"] == _oracle_pick(us_gaap, "Assets", "USD", 2024)
    assert row["net_income"] == _oracle_pick(us_gaap, "NetIncomeLoss", "USD", 2024)
    assert row["goodwill"] == _oracle_pick(us_gaap, "Goodwill", "USD", 2024)
    assert row["revenue"] == _oracle_pick(
        us_gaap, "RevenueFromContractWithCustomerIncludingAssessedTax", "USD", 2024
    )


def test_end_to_end_covers_expected_fiscal_years() -> None:
    df = extract_company_year("0001637459", "Kraft Heinz Co", FIXTURE.read_bytes())
    assert set(df["fiscal_year"].to_list()) >= {2023, 2024, 2025}
