# Usage guide

Practical how-to for the four things people actually want to do with this project: run it,
add a company, add a metric, and find the problem companies. For the *why* behind the design,
see `docs/PROJECT_BRIEF.md`; for what was actually built and every bug found along the way, see
`AGENTS.md`.

## Quick start

```bash
make setup    # uv sync
make ingest   # pull the ~20-ticker universe from SEC EDGAR into bronze (live, cached)
make build    # silver normalization (Python/Polars) + dbt build (silver -> gold)
make report   # ranked cross-company red-flag report -> reports/red_flag_report.md
make demo     # Streamlit dashboard at http://localhost:8501
```

`make ingest`/`make build` only need to be re-run when you change the ticker universe or want
fresher filings. `make report`/`make demo` just read whatever's already in
`data/warehouse.duckdb`.

## Adding a company

Edit `src/fin_lakehouse/universe.py`:

```python
UNIVERSE: list[str] = [
    "KHC", "PG", "KO", ...,
    "NKE",  # <- add the ticker here
]
```

Then:

```bash
make ingest   # pulls the new ticker's filings from EDGAR (existing tickers hit cache, fast)
make build    # re-normalizes + rebuilds gold for the whole universe (silver is always
              # rebuilt from scratch from bronze -- cheap, and avoids incremental-update bugs)
make report   # or make demo
```

That's it — no other file needs to change. `build_silver.py` discovers every company under
`data/bronze/cik=*/` automatically and reads the company name straight out of its own filing, so
adding a ticker never requires touching a hardcoded list anywhere else.

**If a new company's data looks wrong** (a metric is unexpectedly null, or the accounting-identity
test fails in `make build`'s `dbt build` step): it's very likely that company uses a different
XBRL tag than the ones already in `src/fin_lakehouse/edgar/concepts.py`'s `CONCEPT_PRIORITY` map
for one of the ~20 fields — this happened repeatedly scaling from 1 to 22 companies (see
`AGENTS.md`'s milestone 2/3/5 logs for the exact pattern). The fix is almost always: inspect the
company's raw `data/bronze/cik=.../companyfacts.json` for the field in question, find the tag it
actually uses, and append it to that field's list in `concepts.py` (append, don't replace — other
companies may still need the existing tags).

## Adding a metric

**A new ratio computed from existing gold fields** (e.g. a new margin or turnover ratio): add it
directly in `transform/models/marts/ratios/fct_company_year_metrics.sql`, in the relevant `--
Section` comment block, following the existing `case when <denominator> != 0 then ... end`
pattern for divide-by-zero safety. If it's a YoY trend, also add it to the `null_metric_flags`
list if it can divide by zero, and to the `metrics_with_prior` CTE if it needs a prior-year LAG.
Then `cd transform && dbt build --profiles-dir profiles` to verify, and add a schema test in
`_ratios__models.yml` if the metric has a sane bound (e.g. `accepted_range`).

**A metric that needs a raw field not yet extracted** (e.g. a new balance-sheet or income-statement
line item): add it to `CONCEPT_PRIORITY` in `src/fin_lakehouse/edgar/concepts.py` with its
candidate XBRL tag(s) in priority order (check `docs/PROJECT_BRIEF.md` §5 for the tag-priority
convention). It'll automatically flow through `silver/normalize.py` into `silver.company_year`
with no other Python changes, then becomes available in `stg_company_year.sql` for the gold layer
to use (add it to that model's `select` list too).

**Either way, write a test with an independently-derived expected value** — hand-compute it from
the raw silver values by plain arithmetic, not by calling the code you're testing. See
`tests/test_gold_metrics.py` for the pattern, and `AGENTS.md` §1.4 for why this is non-negotiable
here: several real bugs (a YoY sign-flip, a stale-schema bug) were only caught because the tests
didn't just check that the code agreed with itself.

## Adding a detector rule

Add a `Rule(...)` entry to `RULE_CATALOGUE` in `src/fin_lakehouse/detector/rules.py`:

```python
Rule(
    rule_id="my_new_rule",
    severity="medium",  # high=3, medium=2, low=1 in the risk_score weighting
    observed_fields=("some_metric",),        # fields this rule reads from the gold row
    default_thresholds={"some_metric_max": 1.5},
    fires_when=lambda row, t: row["some_metric"] > t["some_metric_max"],
    explain=lambda row, t: f"Some metric is {row['some_metric']:.2f}, above {t['some_metric_max']}.",
),
```

A rule automatically evaluates to "not fired, no error" if any of its `observed_fields` is null
for that company-year — you don't need to handle missing data yourself. Add fire/no-fire tests in
`tests/test_rules.py` with hand-built synthetic rows (see the existing rules for the pattern).

## Filtering by problem areas

**In the dashboard** (`make demo` → "Cross-company ranking" view): three filter controls above
the table —

- **Company** — multiselect, empty means all companies
- **Must have fired** — multiselect of rule IDs; the table only shows company-years where *every*
  selected rule fired (e.g. select `goodwill_heavy` + `low_liquidity` to find companies that are
  both goodwill-heavy *and* illiquid in the same year)
- **Min risk score** — slider, filters out anything below the threshold

The filter logic itself lives in `dashboards/app.py`'s `filter_reports()` function, factored out
as a plain function (not tangled up in Streamlit widget code) so it's covered by
`tests/test_dashboard_filters.py` without needing a browser.

**From Python**, the same building blocks work directly against the gold layer, no dashboard
needed:

```python
from fin_lakehouse.detector.data import load_company_year_metrics
from fin_lakehouse.detector.score import build_ranked_report

reports = build_ranked_report(load_company_year_metrics())

# companies with both weak liquidity and heavy goodwill
problem_years = [
    r for r in reports
    if {"goodwill_heavy", "low_liquidity"} <= {res.rule_id for res in r.fired_rules}
]
for r in problem_years:
    print(r.entity_name, r.fiscal_year, r.risk_score)
```

**Via `reports/red_flag_report.md`** (from `make report`): it's a plain Markdown table, sorted by
risk score — `grep` for a rule name or `grep -A6 "GENERAL MILLS"` for a specific company's fired
rules and explanations.

**Directly in SQL** against `data/warehouse.duckdb`, if you want ratios the detector doesn't
already threshold on:

```sql
SELECT entity_name, fiscal_year, current_ratio, debt_to_equity
FROM main_gold.fct_company_year_metrics
WHERE current_ratio < 1.0 AND debt_to_equity > 1.5
ORDER BY current_ratio;
```
