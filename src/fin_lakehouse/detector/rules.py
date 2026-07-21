"""Red-flag rule catalogue (docs/PROJECT_BRIEF.md §7): a typed table of rules over gold
company-year metrics, each a predicate + a plain-English explanation template.

A rule that needs a metric which is null for that company-year (missing upstream data, or --
for real_revenue_decline -- a metric that's out of scope for v1, see AGENTS.md milestone 3 log)
evaluates to not-fired with no explanation, never an error and never a silent false positive.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

Severity = str  # "high" | "medium" | "low"

SEVERITY_WEIGHT: dict[Severity, int] = {"high": 3, "medium": 2, "low": 1}


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    fired: bool
    severity: Severity
    observed_values: dict[str, float | None]
    threshold: dict[str, float]
    explanation: str | None


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: Severity
    observed_fields: tuple[str, ...]
    default_thresholds: dict[str, float]
    fires_when: Callable[[Mapping[str, Any], dict[str, float]], bool]
    explain: Callable[[Mapping[str, Any], dict[str, float]], str]

    def evaluate(
        self, row: Mapping[str, Any], thresholds: dict[str, float] | None = None
    ) -> RuleResult:
        t = {**self.default_thresholds, **(thresholds or {})}
        observed = {field: row.get(field) for field in self.observed_fields}
        if any(value is None for value in observed.values()):
            return RuleResult(self.rule_id, False, self.severity, observed, t, None)
        fired = self.fires_when(row, t)
        explanation = self.explain(row, t) if fired else None
        return RuleResult(self.rule_id, fired, self.severity, observed, t, explanation)


def _fmt_musd(value: float) -> str:
    return f"${value / 1e6:,.0f}M"


RULE_CATALOGUE: tuple[Rule, ...] = (
    Rule(
        rule_id="negative_working_cap",
        severity="high",
        observed_fields=("working_capital",),
        default_thresholds={},
        fires_when=lambda row, t: row["working_capital"] < 0,
        explain=lambda row, t: (
            f"Working capital is negative ({_fmt_musd(row['working_capital'])}) -> "
            "short-term obligations exceed short-term assets."
        ),
    ),
    Rule(
        rule_id="equity_wiped_by_gw",
        severity="high",
        observed_fields=("equity_ex_goodwill",),
        default_thresholds={},
        fires_when=lambda row, t: row["equity_ex_goodwill"] < 0,
        explain=lambda row, t: (
            f"Equity excluding goodwill is negative ({_fmt_musd(row['equity_ex_goodwill'])}) -> "
            "goodwill alone exceeds total equity."
        ),
    ),
    Rule(
        rule_id="goodwill_heavy",
        severity="medium",
        observed_fields=("goodwill_to_assets",),
        default_thresholds={"goodwill_to_assets_max": 0.30},
        fires_when=lambda row, t: row["goodwill_to_assets"] > t["goodwill_to_assets_max"],
        explain=lambda row, t: (
            f"Goodwill is {row['goodwill_to_assets']:.1%} of total assets, above the "
            f"{t['goodwill_to_assets_max']:.0%} threshold."
        ),
    ),
    Rule(
        rule_id="revenue_quality",
        severity="high",
        observed_fields=("dso_yoy", "revenue_yoy", "dso"),
        default_thresholds={"dso_yoy_min": 0.15},
        fires_when=lambda row, t: row["dso_yoy"] > t["dso_yoy_min"] and row["revenue_yoy"] <= 0,
        explain=lambda row, t: (
            f"DSO rose {row['dso_yoy']:+.0%} YoY to {row['dso']:.0f} days while revenue "
            f"{'fell' if row['revenue_yoy'] < 0 else 'was flat'} {row['revenue_yoy']:+.1%} "
            "-> deteriorating revenue quality."
        ),
    ),
    Rule(
        rule_id="ccc_deterioration",
        severity="medium",
        observed_fields=("ccc_yoy", "ccc"),
        default_thresholds={"ccc_yoy_min": 0.20},
        fires_when=lambda row, t: row["ccc_yoy"] > t["ccc_yoy_min"],
        explain=lambda row, t: (
            f"Cash conversion cycle rose {row['ccc_yoy']:+.0%} YoY to {row['ccc']:.0f} days."
        ),
    ),
    Rule(
        rule_id="leverage",
        severity="medium",
        observed_fields=("net_debt", "debt_to_equity"),
        default_thresholds={"debt_to_equity_min": 2.0},
        fires_when=lambda row, t: (
            row["net_debt"] > 0 and row["debt_to_equity"] > t["debt_to_equity_min"]
        ),
        explain=lambda row, t: (
            f"Net debt is {_fmt_musd(row['net_debt'])} and debt-to-equity is "
            f"{row['debt_to_equity']:.2f}, above the {t['debt_to_equity_min']:.1f}x threshold."
        ),
    ),
    Rule(
        rule_id="low_liquidity",
        severity="medium",
        observed_fields=("current_ratio",),
        default_thresholds={"current_ratio_min": 1.0},
        fires_when=lambda row, t: row["current_ratio"] < t["current_ratio_min"],
        explain=lambda row, t: (
            f"Current ratio is {row['current_ratio']:.2f}, below the "
            f"{t['current_ratio_min']:.1f}x threshold."
        ),
    ),
    Rule(
        rule_id="margin_erosion",
        severity="medium",
        observed_fields=("net_margin_yoy", "net_margin"),
        default_thresholds={"net_margin_yoy_max": -0.20},
        fires_when=lambda row, t: row["net_margin_yoy"] < t["net_margin_yoy_max"],
        explain=lambda row, t: (
            f"Net margin moved {row['net_margin_yoy']:+.0%} YoY to {row['net_margin']:.1%}."
        ),
    ),
    Rule(
        rule_id="goodwill_impairment",
        severity="high",
        observed_fields=("goodwill_impairment",),
        default_thresholds={},
        fires_when=lambda row, t: row["goodwill_impairment"] > 0,
        explain=lambda row, t: (
            f"Goodwill impairment of {_fmt_musd(row['goodwill_impairment'])} recognized "
            "this period."
        ),
    ),
    Rule(
        rule_id="real_revenue_decline",
        severity="medium",
        observed_fields=("revenue_real_yoy", "revenue_yoy"),
        default_thresholds={},
        fires_when=lambda row, t: row["revenue_real_yoy"] < 0 and row["revenue_yoy"] >= 0,
        explain=lambda row, t: (
            f"Nominal revenue rose {row['revenue_yoy']:+.1%} YoY but real (CPI-deflated) "
            f"revenue fell {row['revenue_real_yoy']:+.1%} -> growth is inflation only."
        ),
    ),
)
