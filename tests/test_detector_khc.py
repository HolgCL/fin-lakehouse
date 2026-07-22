"""Detector integration tests against real KHC data -- reproduces the qualitative course story
(goodwill-heavy, the FY2018 impairment, periods of weak liquidity), human-confirmed against the
detector's real output (see AGENTS.md milestone 4 log) before being pinned here as expectations.

Since milestone 5, the warehouse holds the full ~20-ticker universe (universe.py), not just KHC
-- every helper here filters to KHC's CIK explicitly, not just by fiscal_year (a bare
{fiscal_year: report} dict silently drops KHC's rows when another company shares the same
fiscal year -- a real bug found scaling this test up, see AGENTS.md milestone 5 log).

Requires `make ingest && make build` to have populated data/warehouse.duckdb first.
"""

from pathlib import Path

import pytest

from fin_lakehouse.detector.data import load_company_year_metrics
from fin_lakehouse.detector.score import build_ranked_report

WAREHOUSE = Path(__file__).parent.parent / "data" / "warehouse.duckdb"
KHC_CIK10 = "0001637459"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(),
    reason="data/warehouse.duckdb not built; run `make ingest && make build` first",
)


def _khc_report_by_year() -> dict[int, object]:
    rows = load_company_year_metrics()
    report = build_ranked_report(rows)
    return {r.fiscal_year: r for r in report if r.cik == KHC_CIK10}


def _fired_ids(report_row: object) -> set[str]:
    return {r.rule_id for r in report_row.fired_rules}  # type: ignore[attr-defined]


def test_goodwill_heavy_fires_almost_every_year() -> None:
    by_year = _khc_report_by_year()
    goodwill_heavy_years = {fy for fy, r in by_year.items() if "goodwill_heavy" in _fired_ids(r)}
    # Every year except FY2025, which dips just under the 30% threshold.
    assert goodwill_heavy_years == set(range(2015, 2025))


def test_goodwill_impairment_fires_2018_through_2025() -> None:
    by_year = _khc_report_by_year()
    impairment_years = {
        fy for fy, r in by_year.items() if "goodwill_impairment" in _fired_ids(r)
    }
    assert impairment_years == set(range(2018, 2026))


def test_fy2018_impairment_is_the_largest() -> None:
    by_year = _khc_report_by_year()
    fy2018 = by_year[2018]
    impairment_result = next(
        r for r in fy2018.fired_rules if r.rule_id == "goodwill_impairment"  # type: ignore[attr-defined]
    )
    assert impairment_result.observed_values["goodwill_impairment"] == pytest.approx(
        7_008_000_000.0
    )


def test_leverage_never_fires_for_khc() -> None:
    """KHC's story is goodwill overvaluation, not a leverage crisis -- debt-to-equity stayed
    well under the 2.0x threshold throughout (confirmed against real data, max ~1.1x)."""
    by_year = _khc_report_by_year()
    assert all("leverage" not in _fired_ids(r) for r in by_year.values())


def test_equity_never_wiped_out_by_goodwill() -> None:
    """Goodwill was large but equity survived every impairment (confirmed, stayed $13-21B)."""
    by_year = _khc_report_by_year()
    assert all("equity_wiped_by_gw" not in _fired_ids(r) for r in by_year.values())


def test_weak_liquidity_years_are_flagged() -> None:
    by_year = _khc_report_by_year()
    low_liquidity_years = {fy for fy, r in by_year.items() if "low_liquidity" in _fired_ids(r)}
    assert low_liquidity_years == {2016, 2017, 2021, 2022, 2023}


def test_2022_and_2023_are_khcs_highest_risk_years() -> None:
    """Not FY2018 -- 2022/2023 compound negative working capital, weak liquidity, CCC
    deterioration, ongoing impairment, and goodwill-heaviness. Human-confirmed real finding,
    among KHC's own fiscal years (not a claim about ranking against other universe companies)."""
    by_year = _khc_report_by_year()
    ranked = sorted(by_year.values(), key=lambda r: r.risk_score, reverse=True)  # type: ignore[attr-defined]
    top_two = {ranked[0].fiscal_year, ranked[1].fiscal_year}  # type: ignore[attr-defined]
    assert top_two == {2022, 2023}
    assert ranked[0].risk_score == pytest.approx(50.0)  # type: ignore[attr-defined]
    assert ranked[1].risk_score == pytest.approx(50.0)  # type: ignore[attr-defined]


def test_real_revenue_decline_never_fires_no_cpi_data() -> None:
    by_year = _khc_report_by_year()
    assert all("real_revenue_decline" not in _fired_ids(r) for r in by_year.values())
