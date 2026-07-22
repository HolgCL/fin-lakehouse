"""Streamlit gold explorer + red-flag report (docs/PROJECT_BRIEF.md §9 milestone 6).

Reads directly from data/warehouse.duckdb and reuses detector/score.py -- no logic duplicated
between the CLI report (report.py) and this dashboard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.express as px
import streamlit as st

from fin_lakehouse.detector.data import load_company_year_metrics
from fin_lakehouse.detector.rules import RULE_CATALOGUE
from fin_lakehouse.detector.score import build_ranked_report

ALL_RULE_IDS = [rule.rule_id for rule in RULE_CATALOGUE]

WAREHOUSE_PATH = Path("data/warehouse.duckdb")

CHARTABLE_METRICS = [
    "goodwill_to_assets",
    "current_ratio",
    "debt_to_equity",
    "net_margin",
    "working_capital",
    "ccc",
]


def _fmt(value: Any, spec: str = ".2f") -> str:
    return format(value, spec) if value is not None else "—"


def _fmt_cell(value: Any) -> str:
    """Stringify every cell so the "value" column is a single Arrow-compatible dtype -- a
    mix of floats and a list (null_metric_flags) in one column fails to serialize otherwise."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.4f}"
    return str(value)


@st.cache_data
def _load_rows() -> list[dict[str, Any]]:
    return load_company_year_metrics(WAREHOUSE_PATH)


def render_company_explorer(rows: list[dict[str, Any]], companies: list[str]) -> None:
    company = st.sidebar.selectbox("Company", companies)
    company_rows = sorted(
        (r for r in rows if r["entity_name"] == company), key=lambda r: r["fiscal_year"]
    )
    years = [r["fiscal_year"] for r in company_rows]
    fy = st.sidebar.selectbox("Fiscal year", years, index=len(years) - 1)
    row = next(r for r in company_rows if r["fiscal_year"] == fy)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current ratio", _fmt(row["current_ratio"]))
    col2.metric("Debt/Equity", _fmt(row["debt_to_equity"]))
    col3.metric("Goodwill/Assets", _fmt(row["goodwill_to_assets"], ".1%"))
    col4.metric("Net margin", _fmt(row["net_margin"], ".1%"))

    metric_choice = st.selectbox("Metric to chart across years", CHARTABLE_METRICS)
    chart_rows = [
        {"fiscal_year": r["fiscal_year"], metric_choice: r[metric_choice]} for r in company_rows
    ]
    fig = px.line(
        chart_rows, x="fiscal_year", y=metric_choice, markers=True,
        title=f"{company}: {metric_choice}",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"All gold metrics — {company} FY{fy}")
    metric_fields = [k for k in row if k not in ("cik", "entity_name", "fiscal_year")]
    # null_metric_flags is a list, not a scalar -- stringify it so the "value" column stays a
    # single Arrow-compatible type (a float/list mix otherwise fails to serialize).
    st.dataframe(
        [{"metric": k, "value": _fmt_cell(row[k])} for k in metric_fields],
        use_container_width=True,
        hide_index=True,
    )


def filter_reports(
    reports: list[Any],
    company_filter: list[str],
    rule_filter: list[str],
    min_score: float,
) -> list[Any]:
    """Pure filter predicate, factored out so it's unit-testable without Streamlit widgets."""
    return [
        r
        for r in reports
        if r.risk_score >= min_score
        and (not company_filter or r.entity_name in company_filter)
        and (not rule_filter or set(rule_filter) <= {res.rule_id for res in r.fired_rules})
    ]


def render_cross_company_ranking(reports: list[Any], companies: list[str]) -> None:
    st.subheader("Red-flag ranked report — filter by problem area")

    col1, col2, col3 = st.columns([2, 2, 1])
    company_filter = col1.multiselect("Company (empty = all)", companies)
    rule_filter = col2.multiselect(
        "Must have fired (empty = any)", ALL_RULE_IDS,
        help="Only show company-years where every selected rule fired.",
    )
    min_score = col3.slider("Min risk score", 0, 100, 0)

    filtered = filter_reports(reports, company_filter, rule_filter, min_score)
    st.caption(f"{len(filtered)} of {len(reports)} company-years match")

    table = [
        {
            "Company": r.entity_name,
            "FY": r.fiscal_year,
            "Risk score": round(r.risk_score, 1),
            "Fired rules": ", ".join(res.rule_id for res in r.fired_rules) or "—",
        }
        for r in filtered
    ]
    st.dataframe(table, use_container_width=True, height=600, hide_index=True)


def render_rule_drilldown(reports: list[Any]) -> None:
    labels = [f"{r.entity_name} — FY{r.fiscal_year} (score {r.risk_score:.1f})" for r in reports]
    idx = st.selectbox("Company-year", range(len(reports)), format_func=lambda i: labels[i])
    report = reports[idx]
    if not report.fired_rules:
        st.info("No rules fired for this company-year.")
        return
    for res in report.fired_rules:
        with st.container(border=True):
            st.markdown(f"**[{res.severity}] {res.rule_id}**")
            st.write(res.explanation)
            st.json(res.observed_values)


def main() -> None:
    st.set_page_config(page_title="fin-lakehouse: red-flag explorer", layout="wide")

    if not WAREHOUSE_PATH.exists():
        st.error("data/warehouse.duckdb not found. Run `make ingest && make build` first.")
        st.stop()

    rows = _load_rows()
    reports = build_ranked_report(rows)
    companies = sorted({r["entity_name"] for r in rows})

    st.title("fin-lakehouse: financial red-flag explorer")
    st.caption(
        f"{len(rows)} company-years across {len(companies)} companies (SEC EDGAR, gold layer)"
    )

    view = st.sidebar.radio(
        "View", ["Company explorer", "Cross-company ranking", "Rule drill-down"]
    )
    if view == "Company explorer":
        render_company_explorer(rows, companies)
    elif view == "Cross-company ranking":
        render_cross_company_ranking(reports, companies)
    else:
        render_rule_drilldown(reports)


if __name__ == "__main__":
    main()
