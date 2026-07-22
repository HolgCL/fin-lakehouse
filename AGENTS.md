# AGENTS.md — working agreement for `fin-lakehouse`

This project is run as **agent engineering, not vibe coding**. The human owns the spec, the
contracts, and the correctness oracles; the agent is a fast executor inside those boundaries.
The full spec lives in [`docs/PROJECT_BRIEF.md`](docs/PROJECT_BRIEF.md) — read it before starting
any task. This file is the durable protocol; keep it updated as the working agreement evolves.

## Ground rules

1. **The human owns the spec and the contracts.** Data schemas, function signatures, XBRL tag
   priorities, metric definitions, rule thresholds are decided in the project brief or by the
   human before code is written. On any design fork not covered there (e.g. how to average
   balances for CCC, dbt model granularity), **stop, state 2–3 options with a recommendation,
   and wait for a decision.** Do not resolve architecture by taste.

2. **Plan before code, on every milestone.** Post a short plan — files touched, approach, how it
   will be verified — and wait for approval before implementing. No plan, no code.

3. **Small, reviewable diffs.** One milestone = one coherent change set. Show the diff and stop.
   Never dump many unreviewed files at once. Conventional-commit messages. Every diff should be
   justifiable line by line, as if reviewed by a human like a PR from a junior engineer.

4. **Tests are the spec, and their oracles come from the human — not the agent.** The failure
   mode being engineered against: the agent writing both a metric and its "expected" value from
   the same code path, so the test only proves the code agrees with itself.
   - Expected values in metric tests must come from an independent source: a hand-computed number
     the human provides, or a figure derived by a *different method* than the production code
     (e.g. hand-written arithmetic on raw line items in the test, not a call into the metric
     function under test).
   - For Kraft Heinz (`KHC`) fixtures specifically, ask the human to confirm oracle numbers before
     asserting on them. Any self-generated expected value must be marked
     `# UNVERIFIED — needs human oracle` and flagged for review; it must never sit silently in a
     passing test.

5. **Verification gates are objective, but green ≠ correct.** Before presenting a diff, run
   `ruff`, `mypy`, `pytest`, and (once it exists) `dbt build`. These prove self-consistency, not
   domain correctness — that judgment call belongs to the human at each review gate.

6. **Fail loud, never silent.** A missing XBRL tag is a warning naming the company and year, never
   a silent coercion to 0. Division by zero is a null plus a flag, never a silent number. Every
   assumption made along the way is written into the run log and the PR note.

7. **Context hygiene.** The spec lives in the repo, not in chat memory. Prefer a fresh session per
   milestone that re-reads `docs/PROJECT_BRIEF.md` and this file, over one long drifting thread.

8. **Reversibility.** Every change must be revertable with a single `git revert`. No irreversible
   actions — force-push, history rewrite, deleting `data/` — without explicit approval.

## Self-check before presenting any diff

- Can every line be justified?
- Do the test oracles come from an independent source the human has confirmed?
- Does the pipeline fail loudly on bad input, rather than silently producing a wrong number?
- Can this change be reverted in one command?

If any answer is "no," it is not ready to show.

## Milestone rhythm

Each milestone in `docs/PROJECT_BRIEF.md` §9 follows: **PLAN → approve → small diff → self-verify
→ STOP for human review.** Do not proceed to the next milestone without an explicit go-ahead.

## Verification commands

```bash
make lint   # ruff check + mypy
make test   # pytest
make build  # dbt build (once transform/ has models — milestone 3+)
```

## Milestone log

- **Milestone 0**: repo scaffold, tooling config, CI skeleton, README stub,
  `AGENTS.md`. No pipeline logic yet — `config.py` only, plus placeholder package `__init__.py`
  files under `src/fin_lakehouse/{edgar,bronze,silver,detector}/` establishing the layout from
  brief §8. `ruff`, `mypy`, `pytest` all green on this minimal surface.
- **Milestone 1**: `edgar/client.py` (UA header, retry+backoff+jitter, ~10 req/s rate limit,
  on-disk cache), `edgar/cik.py` (ticker→CIK resolution), `bronze/land.py` (verbatim landing,
  partitioned `cik={cik10}/landed={date}` — see brief §8 note on the "filed" partition being
  ambiguous for a whole-history payload; resolved as ingestion date, human-confirmed).
  `ingest.py` wires these into `make ingest`. Ran a real live pull for KHC (CIK `0001637459`,
  "Kraft Heinz Co") to prove the path end to end and to source `tests/fixtures/*.json` — trimmed
  but real SEC data, not fabricated. All 15 tests run against the fixtures via
  `httpx.MockTransport`, never the live API.
- **Milestone 2**: `edgar/concepts.py` (§5 tag-priority map), `silver/normalize.py`
  (tag-priority extraction + dedup into a tidy company-year table), `silver/load.py` (persists
  to `silver.company_year` in `data/warehouse.duckdb`, replace-on-write for idempotency),
  `build_silver.py` wired into `make build`. Findings against real KHC data, all human-confirmed
  before coding:
  - Three fields (`revenue`, `payables`, `long_term_debt`) don't resolve via any of §5's listed
    tags for KHC. Appended real fallback tags after the spec tags (spec tags still win when
    present): `RevenueFromContractWithCustomerIncludingAssessedTax` + `SalesRevenueGoodsNet`
    (revenue, together give full 2015–2025 coverage), `AccountsPayableTradeCurrent` (payables),
    `LongTermDebtAndCapitalLeaseObligations` (long_term_debt).
  - Dedup rule for facts sharing `(concept, fiscal_year)`: latest `end` wins (discards
    same-filing prior-year comparatives), latest `filed` breaks ties (captures restatements).
  - Two bugs found and fixed via the real live run, each confirmed before fixing: (1) duration
    facts (income-statement concepts) need a ~350–380 day span filter before dedup — without it,
    a single 10-K's Q4-only fact can share the exact `end` date as the true annual figure and
    silently get treated as a "conflicting" duplicate (real example: KHC FY2016
    `SalesRevenueGoodsNet` had a $26.5B annual fact and a $6.9B Q4-only fact both under
    `end=2016-12-31`); (2) as a final tiebreak when a genuine duration fact still ties with a
    stray instant-tagged fact under the same tag (e.g. KHC FY2018 `GoodwillImpairmentLoss`),
    prefer the entry that has a `start` field. Both are covered by regression tests reproducing
    the exact real values. `ruff`, `mypy`, `pytest` (28 tests) all green; `make build` against
    the real KHC bronze snapshot reproduces the known FY2018 story (net loss ≈ $10.2B, $7.0B
    goodwill impairment) with no unresolved conflicts.
- **Milestone 3**: dbt project (`transform/`) on dbt-duckdb — `stg_company_year` (1:1 passthrough),
  `int_company_year_with_prior` (LAG for CCC averaging + YoY), `fct_company_year_metrics` (one
  wide mart, every §6 metric as a column, human-confirmed granularity decision over several
  narrow marts). `revenue_real_yoy` and `break_even` are out of scope per §6 (no CPI seed table,
  no fixed/variable split) — skipped, not fabricated. Divide-by-zero → null metric + the metric's
  name recorded in a `null_metric_flags` list column (human-confirmed design, one column not ~25
  booleans). Schema tests use a hand-rolled `accepted_range` macro instead of dbt-utils, to keep
  `git clone` reproducibility dependency-free (no `dbt deps` network fetch). CI runs the real live
  SEC pipeline (`make ingest && make build`) rather than a fixture-only warehouse — human-confirmed,
  since EDGAR is free/unauthenticated (the `SEC_USER_AGENT` contact email in `ci.yml` is disclosure
  to SEC, not a secret).
  - **Accounting-identity test, two real findings, both human-confirmed:** (1) `assets =
    liabilities + equity` failed for all 11 KHC fiscal years using only the gold `equity` field
    (parent-only `StockholdersEquity`) — real gaps of ~$120–220M (noncontrolling interest) most
    years and $8.55B in FY2015 (temporary/mezzanine equity from the Kraft-Heinz merger's preferred
    financing, confirmed via `LiabilitiesAndStockholdersEquity` tying to `Assets` exactly). Fixed
    by extracting `minority_interest` and `temporary_equity` as new silver fields — defaulting to
    0 when absent (`ZERO_DEFAULT_FIELDS` in `concepts.py`, not logged as missing, since 0 is
    legitimately correct for companies without these) — used only by the identity test, not
    exposed as gold metrics since they're outside §6. (2) The remaining residual (up to ~0.044%
    of total assets, from further obscure components like redeemable NCI) is immaterial rounding
    noise, not a bug — switched the tolerance from a flat $1M absolute to 0.1% of `total_assets`
    (relative), since an absolute dollar tolerance doesn't scale across company sizes and a real
    extraction bug would produce a gap orders of magnitude larger than a few basis points.
  - Oracle for `tests/test_gold_metrics.py`: 10 KHC FY2018 values (current_ratio, quick_ratio,
    working_capital, debt_to_equity, goodwill_to_assets, equity_ex_goodwill, DSO, net_margin,
    normalized_net_income, net_debt) hand-computed from the real silver FY2017/FY2018 raw values
    by plain arithmetic (not via any production code path) and human-confirmed before being
    trusted as test assertions, per §1.4. All matched the dbt-built values exactly once the
    identity-test bugs above were fixed.
  - `ruff`, `mypy`, `pytest` (34 tests) and `dbt build` (11/11 pass) all green. `make build`
    reproduces the flagship KHC FY2018 story end to end: goodwill 35.3% of assets, equity
    survives ex-goodwill ($15.2B) but net income is still negative even normalized for the
    impairment (-$3.2B) — a genuine operating problem beyond the write-down itself.
- **Milestone 4**: `detector/rules.py` (typed `Rule` dataclass table, all 10 rules from §7),
  `detector/score.py` (risk_score = 100 × fired-severity-weight / total-catalogue-weight,
  high=3/medium=2/low=1, human-confirmed formula), `detector/data.py` (loads the gold table).
  Two bugs found via the real live run, both human-confirmed before fixing:
  - **§6/§7 inconsistency**: `margin_erosion` needs `net_margin_yoy`, but §6's YoY list only
    specifies `gross_margin_yoy`. Added `net_margin_yoy` to `fct_company_year_metrics` (same LAG
    pattern as the other 5 trend features). Also found `goodwill_impairment` itself wasn't
    exposed as a gold column (only used internally for `normalized_net_income`) — added as a
    passthrough, needed by the `goodwill_impairment` rule.
  - **YoY sign-flip bug** (real, and pre-existing in already-shipped milestone-3 code): the naive
    `(current - prior) / prior` formula sign-flips when `prior` is negative. FY2019 net margin
    actually *improved* from -38.8% to +7.75% (a real recovery), but the old formula computed
    -120% ("erosion") because it divided by a negative prior. Fixed by dividing by `abs(prior)`
    across all 7 YoY columns, not just the new one — positive now always means improvement, even
    across a zero-crossing.
  - **Stale schema bug**: adding `+schema: gold` mid-development left orphaned copies of the mart
    behind in the old `main` schema (dbt doesn't drop old locations on a schema-config change). A
    "pick the first matching schema" discovery query in both `detector/data.py` and
    `tests/test_gold_metrics.py` silently read the stale, pre-fix copy — explaining why
    `goodwill_impairment` and `margin_erosion` didn't fire in the first real run. Fixed by
    deleting the (gitignored, fully rebuildable) stale warehouse and hardcoding the known
    `main_gold` schema in both readers instead of discovering it dynamically.
  - **KHC story, human-confirmed against real detector output**: `goodwill_heavy` fires nearly
    every year (32–37% of assets, all but FY2025); `goodwill_impairment` fires FY2018–2025 (8
    straight years), headlined by the $7.0B FY2018 and a second $6.7B FY2025 write-down;
    `leverage` never fires (debt-to-equity stayed under ~1.1x, well below the 2.0x threshold —
    KHC's problem was goodwill overvaluation, not leverage); `equity_wiped_by_gw` never fires
    (equity survived every impairment, $13–21B ex-goodwill); highest risk years are **2022/2023**
    (score 50, compounding negative working capital + weak liquidity + CCC deterioration), not
    FY2018 (score 29.2 — goodwill-heavy + margin erosion + the impairment, but liquidity was fine
    that specific year). Matches the qualitative course analysis.
  - `ruff`, `mypy`, `pytest` (56 tests) and `dbt build` (11/11) all green.
- **Milestone 5**: `universe.py` (human-confirmed 22-ticker list — consumer staples, tech,
  industrials/autos, retail, telecom/media; deliberately includes GE, T, BA, INTC for their real
  documented red flags, not just clean blue-chips), `ingest.py` (`ingest_tickers`: one shared
  `EdgarClient` across the whole run so the rate limiter actually governs it, not reset per
  ticker; continues past a single ticker's failure, raises with the full failure list at the
  end), `build_silver.py` (discovers every landed CIK from bronze, reads `entityName` from each
  snapshot's own JSON instead of a hardcoded constant, one combined `write_company_year` call —
  silver stays fully rebuildable from bronze at any universe size), `report.py` (ranked
  cross-company Markdown report, `reports/red_flag_report.md`, gitignored/regenerated like
  `data/`, human-confirmed).
  - **Real bug, `Null` vs `Float64` dtype**: concatenating companies crashed
    (`polars.exceptions.SchemaError`) because a company with an entirely-null field (e.g. one
    that never reports `short_term_debt`) makes polars infer that column as `Null` instead of
    `Float64`, conflicting with companies that do have data there. Fixed with an explicit schema
    in `extract_company_year` (`silver/normalize.py`) instead of letting polars infer dtypes from
    data — `tests/test_build_silver.py` pins this exact scenario as a regression test.
  - **Real accounting-identity gaps at scale, both traced to exact tags, human-confirmed**: (1)
    General Mills' up-to-4.27%-of-assets gap and GE's up-to-0.9%/$3.4B gap both matched a
    "redeemable noncontrolling interest" concept, just tagged differently per filer —
    `RedeemableNoncontrollingInterestEquityCarryingAmount` (GE, same tag as KHC's tiny residual)
    and `RedeemableNoncontrollingInterestEquityOtherFairValue` (General Mills). Added both to
    `temporary_equity`'s tag list. (2) PepsiCo's remaining ~0.15–0.26% residual traced to an
    inconsistency in PepsiCo's *own* filed XBRL — their
    `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` doesn't reconcile
    with the sum of their own filed `StockholdersEquity` + `MinorityInterest` — not a missing
    concept on our end, nothing further to extract. Bumped the accounting-identity tolerance from
    0.1% to 0.3% of `total_assets`, clearing all 342 company-years across the full universe.
  - **CI scope, human-confirmed**: CI's live ingest step stays KHC-only
    (`uv run python -m fin_lakehouse.ingest KHC`, bypassing the Makefile's new universe default)
    to keep CI fast and light on SEC's servers — the full-universe path is exercised locally and
    by offline unit tests (`test_universe.py`, `test_ingest.py`, `test_build_silver.py`,
    `test_report.py`) that mock the network or use synthetic bronze snapshots.
  - **Real cross-company findings, sanity-checked against known history**: General Mills is the
    highest-risk company in the universe — genuinely negative `equity_ex_goodwill` in *every*
    year 2010–2026 (goodwill $6.6–15.6B against equity of only $4.3–10.5B, especially after the
    2018 Blue Buffalo acquisition) plus debt-to-equity consistently 1.9–3.8x, a structural pattern
    rather than an isolated bad year like KHC's. GE FY2018 (`equity_wiped_by_gw`, `margin_erosion`,
    `goodwill_impairment`), AT&T FY2020 (`negative_working_cap`, `low_liquidity`, `margin_erosion`,
    `goodwill_impairment`), Boeing FY2024 (`equity_wiped_by_gw`, `revenue_quality`,
    `margin_erosion`), and Intel FY2012 (`revenue_quality`, `goodwill_impairment`) all fired
    real, defensible flags matching their documented histories. Several mature consumer-staples
    names (PepsiCo, Colgate, P&G, Mondelez) also show `equity_wiped_by_gw`/`negative_working_cap`
    frequently — a known characteristic of shareholder-return-focused blue-chips running thin or
    negative book equity from aggressive buybacks, not necessarily distress; noted here rather
    than tuned away, since the rules fire exactly as specified in the brief.
  - `ruff`, `mypy`, `pytest` (66 tests) and `dbt build` (11/11, full 22-ticker/342-row universe)
    all green.
