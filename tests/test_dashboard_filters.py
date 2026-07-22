"""Unit tests for dashboards/app.py's pure filter predicate -- the dashboard itself isn't
covered by pytest (it's Streamlit UI glue), but the actual filtering logic is factored out into
a plain function so it can be verified deterministically, without a browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "dashboards"))

from app import filter_reports  # noqa: E402


def _report(entity_name: str, fiscal_year: int, risk_score: float, fired_rule_ids: list[str]):
    class _Result:
        def __init__(self, rule_id: str) -> None:
            self.rule_id = rule_id

    class _Report:
        def __init__(self) -> None:
            self.entity_name = entity_name
            self.fiscal_year = fiscal_year
            self.risk_score = risk_score
            self.fired_rules = [_Result(rid) for rid in fired_rule_ids]

    return _Report()


def test_no_filters_returns_everything() -> None:
    reports = [_report("A", 2020, 10.0, []), _report("B", 2021, 20.0, ["low_liquidity"])]
    assert filter_reports(reports, [], [], 0) == reports


def test_min_score_filter() -> None:
    reports = [_report("A", 2020, 10.0, []), _report("B", 2021, 50.0, [])]
    result = filter_reports(reports, [], [], 25)
    assert [r.entity_name for r in result] == ["B"]


def test_company_filter() -> None:
    reports = [_report("A", 2020, 10.0, []), _report("B", 2021, 10.0, [])]
    result = filter_reports(reports, ["A"], [], 0)
    assert [r.entity_name for r in result] == ["A"]


def test_rule_filter_requires_all_selected_rules_fired() -> None:
    reports = [
        _report("A", 2020, 10.0, ["low_liquidity"]),
        _report("B", 2021, 10.0, ["low_liquidity", "goodwill_heavy"]),
    ]
    result = filter_reports(reports, [], ["low_liquidity", "goodwill_heavy"], 0)
    assert [r.entity_name for r in result] == ["B"]


def test_filters_combine_with_and() -> None:
    reports = [
        _report("A", 2020, 80.0, ["low_liquidity"]),
        _report("A", 2021, 10.0, ["low_liquidity"]),
        _report("B", 2020, 80.0, ["low_liquidity"]),
    ]
    result = filter_reports(reports, ["A"], ["low_liquidity"], 50)
    assert len(result) == 1
    assert result[0].fiscal_year == 2020
