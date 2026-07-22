-- Accounting identity: assets = liabilities + equity, within a 0.3% relative tolerance
-- (docs/PROJECT_BRIEF.md §3, §9). equity here includes minority_interest and temporary_equity
-- (noncontrolling interest / mezzanine equity) alongside the gold `equity` field (parent-only
-- StockholdersEquity) -- Assets is reported inclusive of those, so the identity only holds
-- exactly if they're included too. Real for KHC: ~$120-220M NCI most years, $8.3B temporary
-- equity in FY2015 from the Kraft-Heinz merger's preferred financing (human-confirmed, see
-- AGENTS.md milestone 3 log). temporary_equity's tag list was extended at milestone 5 scale-out
-- to also cover RedeemableNoncontrollingInterestEquityCarryingAmount (GE) and
-- RedeemableNoncontrollingInterestEquityOtherFairValue (General Mills) -- different filers tag
-- essentially the same "redeemable NCI" concept differently (human-confirmed, see AGENTS.md
-- milestone 5 log).
--
-- Tolerance is relative (0.3% of total_assets), not a flat dollar amount, human-confirmed:
-- traced every remaining residual across the full 22-ticker universe (milestone 5) to either
-- immaterial rounding (KHC, up to ~0.044% of assets) or, for PepsiCo's ~0.15-0.26% residual, an
-- inconsistency in PepsiCo's *own* filed XBRL (their StockholdersEquityIncludingPortionAttributable
-- ToNoncontrollingInterest doesn't reconcile with the sum of their own filed StockholdersEquity +
-- MinorityInterest) -- not a missing concept on our end, nothing further to extract. 0.3% clears
-- every real residual found while staying orders of magnitude tighter than an actual extraction
-- bug would produce.
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
      ) / abs(total_assets) > 0.003
