"""Renders the cross-company ranked red-flag report as Markdown (docs/PROJECT_BRIEF.md §9
milestone 5). Regenerated from live data each run -- gitignored, not a committed snapshot.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fin_lakehouse.detector.data import load_company_year_metrics
from fin_lakehouse.detector.score import CompanyYearReport, build_ranked_report

REPORT_PATH = Path("reports/red_flag_report.md")
TOP_N_EXPLANATIONS = 20


def render_markdown(reports: list[CompanyYearReport]) -> str:
    lines = [
        "# Red-Flag Report",
        "",
        f"Generated {dt.date.today().isoformat()} | {len(reports)} company-years scored | "
        f"{len({r.cik for r in reports})} companies",
        "",
        "| Rank | Company | FY | Risk Score | Fired Rules |",
        "|---|---|---|---|---|",
    ]
    for rank, r in enumerate(reports, start=1):
        fired = ", ".join(f"{res.rule_id} ({res.severity})" for res in r.fired_rules) or "—"
        lines.append(
            f"| {rank} | {r.entity_name} | {r.fiscal_year} | {r.risk_score:.1f} | {fired} |"
        )

    shown = min(TOP_N_EXPLANATIONS, len(reports))
    lines += ["", f"## Explanations (top {shown} by risk_score)", ""]
    for r in reports[:TOP_N_EXPLANATIONS]:
        if not r.fired_rules:
            continue
        lines.append(f"### {r.entity_name} — FY{r.fiscal_year} (risk_score {r.risk_score:.1f})")
        for res in r.fired_rules:
            lines.append(f"- **[{res.severity}] {res.rule_id}**: {res.explanation}")
        lines.append("")

    return "\n".join(lines)


def build_report(output_path: Path = REPORT_PATH) -> Path:
    rows = load_company_year_metrics()
    reports = build_ranked_report(rows)
    markdown = render_markdown(reports)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown)
    return output_path


def main() -> None:
    path = build_report()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
