-- Accounting identity: assets = liabilities + equity, within a 0.1% relative tolerance
-- (docs/PROJECT_BRIEF.md §3, §9). equity here includes minority_interest and temporary_equity
-- (noncontrolling interest / mezzanine equity) alongside the gold `equity` field (parent-only
-- StockholdersEquity) -- Assets is reported inclusive of those, so the identity only holds
-- exactly if they're included too. Real for KHC: ~$120-220M NCI most years, $8.3B temporary
-- equity in FY2015 from the Kraft-Heinz merger's preferred financing (human-confirmed, see
-- AGENTS.md milestone 3 log).
--
-- Tolerance is relative (0.1% of total_assets), not a flat dollar amount, human-confirmed: the
-- remaining residual after including NCI/temporary equity is immaterial rounding/reclassification
-- noise from further obscure XBRL components (e.g. redeemable NCI) that scales with balance-sheet
-- size -- observed up to ~0.044% of assets for KHC, comfortably under this threshold, whereas a
-- real extraction bug would produce a gap orders of magnitude larger.
--
-- Returns offending rows; dbt fails the test if any are found. Skips rows where any of the three
-- core fields is missing -- that gap is already flagged loudly at the silver layer
-- (silver.missing_field) and isn't this test's concern.
select
    cik,
    fiscal_year,
    total_assets,
    total_liabilities,
    equity,
    minority_interest,
    temporary_equity,
    abs(
        total_assets - (total_liabilities + equity + minority_interest + temporary_equity)
    ) as identity_gap
from {{ ref('stg_company_year') }}
where total_assets is not null
  and total_liabilities is not null
  and equity is not null
  and total_assets != 0
  and abs(
        total_assets - (total_liabilities + equity + minority_interest + temporary_equity)
      ) / abs(total_assets) > 0.001
