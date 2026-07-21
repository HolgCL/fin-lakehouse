# fin-lakehouse

A local-first, zero-cost financial-statement lakehouse built on **SEC EDGAR + DuckDB + Polars + dbt**,
with a rules-based **red-flag detector** on top that flags deterioration in a company's financials
(goodwill risk, liquidity squeeze, revenue-quality issues, leverage) with a plain-English explanation.

Case study: Kraft Heinz (`KHC`) — 2018-2019 goodwill write-down.

## Why

Public XBRL filings are messy, inconsistent across companies and years, and hard to compare
without a normalization layer. This project builds that layer end to end: raw filings → tidy
per-company-year facts → analytical ratios → an explainable risk score, with every step
reproducible from a cold clone and every metric backed by a test with an independently-verified
expected value (see `AGENTS.md` for why that matters).

## Architecture

> Mermaid diagram — added in milestone 6.

Medallion layout:

- **Bronze** — raw SEC EDGAR company-facts JSON, landed verbatim, partitioned by CIK.
- **Silver** — tag-priority extraction into a tidy `company_year` table (see `docs/PROJECT_BRIEF.md` §5).
- **Gold** — dbt models computing liquidity, cash-conversion-cycle, solvency, efficiency, and
  quality metrics (§6), plus the red-flag rule catalogue (§7).

## How to run

> Filled in as each milestone lands. Target end state:

```bash
git clone <repo>
cd fin-lakehouse
make setup    # uv sync
make ingest   # pull KHC (+ later, a ~20-ticker universe) from EDGAR into bronze
make build    # dbt build: silver -> gold
make test     # ruff + mypy + pytest + dbt tests
make demo     # Streamlit gold explorer
```

Requires only Python 3.12 (managed via `uv`) and internet access for the first `make ingest`.
No paid cloud services.

## Status

Milestone 0 — repo scaffold and tooling. See `docs/PROJECT_BRIEF.md` for the full spec and
`AGENTS.md` for the working agreement this project is built under.
