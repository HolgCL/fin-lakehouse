from fin_lakehouse.detector.rules import RuleResult
from fin_lakehouse.detector.score import CompanyYearReport
from fin_lakehouse.report import render_markdown


def _report(
    entity_name: str, fiscal_year: int, risk_score: float, fired: bool
) -> CompanyYearReport:
    result = RuleResult(
        rule_id="low_liquidity",
        fired=fired,
        severity="medium",
        observed_values={"current_ratio": 0.5},
        threshold={"current_ratio_min": 1.0},
        explanation="Current ratio is 0.50, below the 1.0x threshold." if fired else None,
    )
    return CompanyYearReport(
        cik="0000000001",
        entity_name=entity_name,
        fiscal_year=fiscal_year,
        risk_score=risk_score,
        rule_results=(result,),
    )


def test_render_markdown_includes_ranked_table_and_explanations() -> None:
    reports = [
        _report("Risky Co", 2020, 50.0, fired=True),
        _report("Safe Co", 2020, 0.0, fired=False),
    ]
    markdown = render_markdown(reports)
    assert "| 1 | Risky Co | 2020 | 50.0 |" in markdown
    assert "| 2 | Safe Co | 2020 | 0.0 |" in markdown
    assert "low_liquidity" in markdown
    assert "Current ratio is 0.50" in markdown


def test_render_markdown_handles_no_fired_rules() -> None:
    reports = [_report("Safe Co", 2020, 0.0, fired=False)]
    markdown = render_markdown(reports)
    assert "| 1 | Safe Co | 2020 | 0.0 | — |" in markdown


def test_render_markdown_caps_explanations_at_top_n() -> None:
    reports = [_report(f"Co {i}", 2020, float(100 - i), fired=True) for i in range(25)]
    markdown = render_markdown(reports)
    assert "Co 0" in markdown  # top of the list, explained
    assert "Co 19" in markdown  # 20th, still within TOP_N_EXPLANATIONS
    assert "### Co 20" not in markdown  # beyond the cap, no explanation section
    assert "| 21 | Co 20 |" in markdown  # but still present in the ranked table
