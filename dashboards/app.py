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
from fin_lakehouse.detector.score import build_ranked_report

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
    st.dataframe(
        [{"metric": k, "value": row[k]} for k in metric_fields],
        use_container_width=True,
        hide_index=True,
    )


def render_cross_company_ranking(reports: list[Any]) -> None:
    st.subheader("Red-flag ranked report — all companies, all fiscal years")
    table = [
        {
            "Company": r.entity_name,
            "FY": r.fiscal_year,
            "Risk score": round(r.risk_score, 1),
            "Fired rules": ", ".join(res.rule_id for res in r.fired_rules) or "—",
        }
        for r in reports
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
        render_cross_company_ranking(reports)
    else:
        render_rule_drilldown(reports)


main()
