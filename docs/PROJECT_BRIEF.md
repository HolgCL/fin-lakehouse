# Project Brief — `fin-lakehouse`

> Paste this whole file as the opening context for the coding agent (Claude Code / VS Code).
> It is the single source of truth for scope, architecture, metric definitions, the quality bar,
> **and the way we work together**. This project is run as **agent engineering, not vibe coding**:
> the human owns the spec, the contracts and the correctness oracles; you (the agent) are a fast
> executor inside those boundaries. Read §1 before writing any code.

---

## 0. Role & mission

You are a senior data engineer building a **portfolio-grade financial-statement lakehouse** with a
**red-flag detector** on top. The bar is not "it runs" — it is "a hiring engineer reads the repo and
wants to interview the author." Clean structure, tests that pin real behaviour, typed code, a README
that explains the *why*, reproducibility from a cold `git clone`.

The domain is financial-statement analysis. The metric definitions and red-flag catalogue below are
**normative** — implement them exactly, cite the formula in a docstring. You do not have financial
domain judgement; the human does. When numbers look plausible to you but are domain-nonsense
(DSO of 400 days, "growth" that is only inflation), you will not catch it — so surface intermediate
values and let the human review.

## 1. Operating model — agent engineering (read first, applies to every task)

This is the contract for *how* we build, and it overrides any instinct to just produce code fast.

1. **The human owns the spec and the contracts.** Data schemas, function signatures, XBRL tag
   priorities, metric definitions, rule thresholds — these are decided in this brief or by the human
   before code. If you hit a design fork not covered here (e.g. how to average balances for CCC, dbt
   model granularity), **stop, state 2–3 options with a recommendation, and wait for a decision.**
   Do not resolve architecture "to taste."

2. **Plan before code, on every milestone.** Post a short plan (files you'll touch, the approach, how
   you'll verify) and **wait for approval** before implementing. No plan → no code.

3. **Small, reviewable diffs.** One milestone = one coherent change set, ideally a few files. Show the
   diff and stop. Never dump many unreviewed files at once. Conventional-commit messages. Assume every
   diff is read line-by-line by the human like a PR from a junior — if you can't justify a line, don't write it.

4. **Tests are the spec, and their oracles come from the human — not from you.**
   This is the single most important rule. The failure mode we are engineering *against* is you writing
   both a metric and its "expected" value from the same code path, so the test only proves the code
   agrees with itself.
   - Expected values in metric tests must come from an **independent source**: a hand-computed number
     the human provides, or a figure you derive by a **different method** than the implementation
     (e.g. compute DSO in the test from raw balance-sheet line items by hand-written arithmetic, not by
     calling the production function).
   - For the Kraft Heinz (`KHC`) fixtures, **ask the human to confirm the oracle numbers** before you
     assert on them. Mark any expected value you generated yourself with `# UNVERIFIED — needs human oracle`
     and call it out for review; never leave an unverified oracle silently in a passing test.

5. **Verification you run yourself, gates that are objective.** Before showing a diff, run
   `ruff`, `mypy`, `pytest`, `dbt build`. Iterate against these signals. But green CI ≠ correct — it
   means self-consistent. Correctness against the domain is the human's call at each review gate.

6. **Fail loud, never silent.** Missing XBRL tag → log a warning and surface the company/year, never
   coerce to 0. Divide-by-zero → null + a flag, never a silent number. Any assumption you make is
   printed in the run log and the PR note. Silent success on bad data is treated as a bug.

7. **Context hygiene.** The spec lives in the repo (`docs/PROJECT_BRIEF.md` + `AGENTS.md`), not in chat
   memory. Prefer a **fresh session per milestone** that re-reads those files, over one long drifting
   thread. Keep `AGENTS.md` updated as the working agreement.

8. **Reversibility.** Every change must be revertable with a single `git revert`. No irreversible actions
   (force-push, history rewrite, deleting `data/`) without explicit approval.

**Self-check before you present anything:** Can I justify every line? Do the test oracles come from an
independent source the human confirmed? Does the pipeline fail loudly on bad input? Can this be reverted
in one command? If any answer is "no," it is not ready.

## 2. What we build (one project, two layers)

1. **Lakehouse** — ingest public US company financials from **SEC EDGAR**, land raw XBRL (bronze),
   normalize key line items across fiscal years (silver), compute analytical metrics (gold).
2. **Red-flag detector** — a rules layer over gold that scores each company/period against a catalogue
   of deterioration markers and outputs a ranked, explainable risk report.

Not two repos. The detector is the top of the same medallion pipeline.

## 3. Non-negotiable engineering principles

- **Local-first, zero-cost to run.** End-to-end on a laptop, no paid cloud, using **DuckDB + Polars +
  dbt-duckdb**. Design a clean seam so the *same dbt models* later target **Databricks/Delta**
  (dbt profile `prod`) with no SQL rewrite. Do not hard-couple to Spark.
- **Idempotent & incremental.** Re-running ingestion never duplicates or corrupts. Bronze is append-only
  raw; silver/gold are rebuildable from bronze.
- **Raw is sacred.** Never mutate raw EDGAR JSON. Bronze stores it verbatim, partitioned.
- **No secrets in git.** `.env.example` only.
- **Every metric and every rule is tested**, with oracles per §1.4, plus dbt schema tests
  (`not_null`, `accepted_range`) and an accounting-identity test (assets = liabilities + equity, within tolerance).

## 4. Tech stack

- Python 3.12, deps via `uv` (fallback `pip`+`venv`).
- `polars` (transforms), `duckdb` (local lakehouse engine), `dbt-core` + `dbt-duckdb` (transform layer),
  `httpx` (EDGAR client), `pydantic-settings` (config), `pytest` (tests), `ruff` (lint+format),
  `mypy` (strict on `edgar/`, `silver/`, `detector/`), `structlog` or configured stdlib logging (no `print` in libs).
- Optional viz: `dashboards/` with a **Streamlit/Plotly** gold explorer (portable, demoable without Power BI);
  a Power BI `.pbix` may be added alongside. Default Streamlit unless told otherwise.
- CI: GitHub Actions running `ruff check`, `mypy`, `pytest`, `dbt build` on the DuckDB dev target.

## 5. Data source — SEC EDGAR (exact spec)

- **Ticker → CIK map:** `https://www.sec.gov/files/company_tickers.json` (ticker, CIK, title).
  Zero-pad CIK to 10 digits for facts endpoints.
- **Company facts (primary):** `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json`
  Path of interest: `facts["us-gaap"][<Concept>]["units"][<unit>]` → array with
  `start`, `end`, `val`, `fy`, `fp` (`FY`/`Q1`…), `form` (`10-K`/`10-Q`), `filed`, `frame`.
  Units typically `USD`, `shares`, `USD/shares`.
- **Single concept (optional):** `https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/us-gaap/{Concept}.json`
- **HARD REQUIREMENT — headers.** SEC mandates a descriptive `User-Agent`, e.g.
  `"fin-lakehouse/0.1 (contact: <email>)"`. Requests without it get blocked. Make it configurable.
- **Rate limit:** under ~10 req/s; polite backoff + retry with jitter. Cache the ticker map and each
  companyfacts JSON on disk so re-runs and tests never hit the live API.
- **Reporting basis:** core metrics use annual (`form == "10-K"`, `fp == "FY"`). Keep quarterly available
  but out of scope for v1 gold.

### Concept mapping (silver) — priority list per field, first available wins

| internal field       | candidate us-gaap tags (priority order)                                              |
|----------------------|--------------------------------------------------------------------------------------|
| revenue              | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues`, `SalesRevenueNet` |
| cogs                 | `CostOfGoodsAndServicesSold`, `CostOfRevenue`                                         |
| gross_profit         | `GrossProfit` (else revenue − cogs)                                                   |
| operating_income     | `OperatingIncomeLoss`                                                                 |
| net_income           | `NetIncomeLoss`                                                                       |
| total_assets         | `Assets`                                                                              |
| current_assets       | `AssetsCurrent`                                                                       |
| current_liabilities  | `LiabilitiesCurrent`                                                                  |
| total_liabilities    | `Liabilities`                                                                         |
| equity               | `StockholdersEquity`                                                                  |
| cash                 | `CashAndCashEquivalentsAtCarryingValue`                                               |
| inventory            | `InventoryNet`                                                                        |
| receivables          | `AccountsReceivableNetCurrent`                                                        |
| payables             | `AccountsPayableCurrent`                                                              |
| short_term_debt      | `DebtCurrent`, `ShortTermBorrowings`                                                  |
| long_term_debt       | `LongTermDebtNoncurrent`, `LongTermDebt`                                              |
| goodwill             | `Goodwill`                                                                            |
| goodwill_impairment  | `GoodwillImpairmentLoss`                                                              |
| eps_basic            | `EarningsPerShareBasic`                                                               |
| eps_diluted          | `EarningsPerShareDiluted`                                                             |
| shares_diluted       | `WeightedAverageNumberOfDilutedSharesOutstanding`                                     |

Missing required field → log loudly (§1.6), never coerce to 0.

## 6. Gold metrics (normative — implement exactly)

Per company per fiscal year. Divide-by-zero → null + flag.

**Liquidity**
- `current_ratio = current_assets / current_liabilities`
- `quick_ratio = (current_assets − inventory) / current_liabilities`
- `cash_ratio = cash / current_liabilities`
- `working_capital = current_assets − current_liabilities`

**Cash conversion cycle** (average opening/closing balance where prior year exists, else closing)
- `DIO = inventory / cogs × 365`
- `DSO = receivables / revenue × 365`
- `DPO = payables / cogs × 365`
- `CCC = DIO + DSO − DPO`

**Solvency / capital structure**
- `total_debt = short_term_debt + long_term_debt`
- `net_debt = total_debt − cash`
- `equity_ratio = equity / total_assets`  (autonomy)
- `debt_to_equity = total_liabilities / equity`
- `interest_bearing_debt_share = total_debt / total_liabilities`

**Efficiency & profitability**
- `asset_turnover = revenue / total_assets`
- `gross_margin = gross_profit / revenue`
- `operating_margin = operating_income / revenue`
- `net_margin = net_income / revenue`

**Quality & normalization**
- `goodwill_to_assets = goodwill / total_assets`
- `equity_ex_goodwill = equity − goodwill`  (the "balance without goodwill" test)
- `normalized_net_income = net_income + goodwill_impairment`  (v1: add back the main one-off; document as approximation)

**Trend features (YoY, in gold across years)**
- YoY % for: revenue, net_income, DSO, CCC, gross_margin, net_debt.
- Optional real growth: `revenue_real_yoy` deflated by a small CPI seed table; if absent, skip and note it — do not fabricate.

> `break_even` / margin of safety need a fixed/variable split absent from XBRL. **Out of scope for v1**
> (or a clearly-labelled rough proxy). Do not fake it.

## 7. Red-flag detector (rules over gold)

Declarative rule catalogue (typed Python table or YAML), evaluated per company-year, emitting
`(rule_id, fired, severity, observed_values, threshold, explanation)`. Aggregate into a
`risk_score` (weighted sum of fired severities, normalized 0–100) + a ranked report. Thresholds
configurable; defaults below. Each fired rule emits a plain-English sentence with the numbers.

| rule_id                | fires when                                                                     | severity |
|------------------------|--------------------------------------------------------------------------------|----------|
| `negative_working_cap` | `working_capital < 0`                                                          | high     |
| `equity_wiped_by_gw`   | `equity_ex_goodwill < 0`                                                        | high     |
| `goodwill_heavy`       | `goodwill_to_assets > 0.30`                                                     | medium   |
| `revenue_quality`      | `DSO_yoy > +15%` and `revenue_yoy <= 0`                                         | high     |
| `ccc_deterioration`    | `CCC_yoy > +20%`                                                                | medium   |
| `leverage`             | `net_debt > 0` and `debt_to_equity > 2.0`                                       | medium   |
| `low_liquidity`        | `current_ratio < 1.0`                                                          | medium   |
| `margin_erosion`       | `net_margin_yoy < −20%` (relative)                                              | medium   |
| `goodwill_impairment`  | `goodwill_impairment > 0` in the period                                         | high     |
| `real_revenue_decline` | `revenue_real_yoy < 0` while nominal `revenue_yoy >= 0`                         | medium   |

Example explanation: `"DSO rose +23% YoY to 71 days while revenue fell −4% → deteriorating revenue quality."`

## 8. Repository layout

```
fin-lakehouse/
  pyproject.toml            # uv/pip, ruff, mypy, pytest config
  Makefile                  # make setup | ingest | build | test | lint | demo
  AGENTS.md                 # the working protocol from §1 (created in milestone 0)
  .env.example              # SEC_USER_AGENT=..., DBT_TARGET=dev
  .github/workflows/ci.yml
  README.md                 # architecture diagram, why, how-to-run, screenshots
  docs/PROJECT_BRIEF.md     # this file
  src/fin_lakehouse/
    config.py               # pydantic-settings
    edgar/
      client.py             # httpx: UA header, retry, rate-limit, on-disk cache
      cik.py                # ticker -> CIK resolver
      concepts.py           # tag priority maps (§5)
    bronze/land.py          # write raw companyfacts JSON, partitioned by cik/filed
    silver/normalize.py     # tag-priority extraction -> tidy per-company-year table
    detector/
      rules.py              # typed rule catalogue (§7)
      score.py              # scoring + ranked report
  transform/                # dbt project (dbt-duckdb dev / databricks prod)
    dbt_project.yml
    profiles/               # duckdb (dev) + databricks (prod) targets
    models/
      staging/              # stg_* : 1:1 with silver
      marts/
        ratios/             # metric families (§6)
        red_flags/          # gold consumed by detector
    tests/                  # dbt schema + accounting-identity tests
  data/                     # gitignored: bronze/, warehouse.duckdb, cache/
  dashboards/               # streamlit app and/or power bi + screenshots
  tests/                    # pytest: metric fixtures (human-verified oracles), client, normalizer
```

## 9. Build order (each milestone: PLAN → approve → small diff → self-verify → STOP for human review)

0. **Scaffold & protocol.** Repo, `pyproject.toml`, tooling (ruff/mypy/pytest), Makefile, CI skeleton,
   README stub, and **`AGENTS.md` capturing the §1 operating model**. Verify `make lint test` is green on
   an empty project. STOP, show the tree.
1. **EDGAR client + CIK resolver → bronze.** Pull `KHC` (Kraft Heinz — the course case study) end to end,
   cache to disk. Test the client against a **saved fixture, not the live API**. STOP.
2. **Silver normalization.** Tag-priority extraction → tidy `company_year` table for KHC across all years.
   Missing tags surfaced loudly. STOP.
3. **Gold via dbt.** Metrics from §6 as dbt models on dbt-duckdb + schema tests + accounting-identity test.
   Metric unit tests use **human-confirmed oracles (§1.4)**. `dbt build` + `pytest` green. STOP.
4. **Detector.** Rule catalogue + scoring + ranked report; unit tests per rule with independent fixtures.
   Reproduce the KHC story (goodwill-heavy, impairment, weak liquidity) — human confirms it matches the
   qualitative course analysis. STOP.
5. **Scale out.** Parametrize to a ~20-ticker universe; produce a ranked cross-company red-flag report. STOP.
6. **Demo + polish.** Streamlit/Power BI over gold; README with Mermaid architecture diagram, run
   instructions, screenshots; document the Databricks/Delta `prod` seam. STOP.

## 10. Definition of done

- `git clone` → `make setup ingest build test demo` works on a clean machine with only Python + internet.
- CI green: ruff, mypy, pytest, dbt build.
- README explains architecture, medallion layers, metric definitions, the detector; ≥1 screenshot + Mermaid diagram.
- ≥15 meaningful tests; every gold metric and every detector rule covered by **independently-oracled** tests.
- KHC produces a coherent, explainable red-flag report matching the course analysis, confirmed by the human.
- `AGENTS.md` present and reflects how we actually worked.

## 11. Working agreement (summary — full version goes in AGENTS.md)

- Language of code, comments, commits, README, AGENTS.md: **English**.
- Every milestone: propose a plan, wait for approval, implement a small diff, run the verification gates,
  then stop for review. No skipping the plan or the stop.
- Test oracles come from the human or an independent method — never self-generated by the implementation.
- Fail loud; make assumptions explicit in logs and PR notes.
- Non-trivial forks: options + recommendation, then wait. Don't decide architecture by taste.
- Nothing irreversible without approval; everything revertable in one `git revert`.

**First task:** milestone 0 — scaffold + tooling + green CI + README stub + `AGENTS.md`. Then STOP and show me the tree. Do not start milestone 1.
