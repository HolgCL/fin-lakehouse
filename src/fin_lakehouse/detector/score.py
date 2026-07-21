"""Rule evaluation, risk scoring, and ranked reporting (docs/PROJECT_BRIEF.md §7).

risk_score is a weighted sum of fired-rule severities (high=3, medium=2, low=1), normalized to
0-100 against the full rule catalogue's total weight -- 100 means every rule fired, 0 means none
did. The denominator is fixed by the catalogue (not by how many rules apply to a given
company-year), so scores are comparable across companies. Human-confirmed, see AGENTS.md
milestone 4 log.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fin_lakehouse.detector.rules import RULE_CATALOGUE, SEVERITY_WEIGHT, RuleResult

_MAX_CATALOGUE_WEIGHT = sum(SEVERITY_WEIGHT[rule.severity] for rule in RULE_CATALOGUE)


@dataclass(frozen=True)
class CompanyYearReport:
    cik: str
    entity_name: str
    fiscal_year: int
    risk_score: float
    rule_results: tuple[RuleResult, ...]

    @property
    def fired_rules(self) -> tuple[RuleResult, ...]:
        return tuple(result for result in self.rule_results if result.fired)


def evaluate_company_year(
    row: dict[str, Any], thresholds: dict[str, dict[str, float]] | None = None
) -> CompanyYearReport:
    thresholds = thresholds or {}
    results = tuple(
        rule.evaluate(row, thresholds.get(rule.rule_id)) for rule in RULE_CATALOGUE
    )
    fired_weight = sum(SEVERITY_WEIGHT[result.severity] for result in results if result.fired)
    risk_score = 100.0 * fired_weight / _MAX_CATALOGUE_WEIGHT
    return CompanyYearReport(
        cik=row["cik"],
        entity_name=row["entity_name"],
        fiscal_year=row["fiscal_year"],
        risk_score=risk_score,
        rule_results=results,
    )


def build_ranked_report(
    rows: list[dict[str, Any]], thresholds: dict[str, dict[str, float]] | None = None
) -> list[CompanyYearReport]:
    reports = [evaluate_company_year(row, thresholds) for row in rows]
    return sorted(reports, key=lambda report: report.risk_score, reverse=True)
