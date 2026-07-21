"""Tag-priority map: internal field name -> candidate us-gaap tags, first available wins.

Base list is the normative mapping from docs/PROJECT_BRIEF.md §5. Three fields (revenue,
payables, long_term_debt) have fallback tags appended after human confirmation: KHC's real
XBRL facts don't use any of the brief's originally-listed tags for these fields (see AGENTS.md
milestone 2 log). Spec tags are always tried first; the fallbacks only apply when none of them
have data.
"""

from __future__ import annotations

CONCEPT_PRIORITY: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",  # fallback, confirmed
        "SalesRevenueGoodsNet",  # fallback, confirmed
    ],
    "cogs": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "net_income": [
        "NetIncomeLoss",
    ],
    "total_assets": [
        "Assets",
    ],
    "current_assets": [
        "AssetsCurrent",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
    ],
    "total_liabilities": [
        "Liabilities",
    ],
    "equity": [
        "StockholdersEquity",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
    ],
    "inventory": [
        "InventoryNet",
    ],
    "receivables": [
        "AccountsReceivableNetCurrent",
    ],
    "payables": [
        "AccountsPayableCurrent",
        "AccountsPayableTradeCurrent",  # fallback, confirmed
    ],
    "short_term_debt": [
        "DebtCurrent",
        "ShortTermBorrowings",
    ],
    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",  # fallback, confirmed
    ],
    "goodwill": [
        "Goodwill",
    ],
    "goodwill_impairment": [
        "GoodwillImpairmentLoss",
    ],
    "eps_basic": [
        "EarningsPerShareBasic",
    ],
    "eps_diluted": [
        "EarningsPerShareDiluted",
    ],
    "shares_diluted": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
    # Not in brief §5 / not a gold metric input: extracted only to power the dbt
    # accounting-identity test (assets = liabilities + equity + these), since Assets includes
    # noncontrolling interest and temporary/mezzanine equity that parent-only StockholdersEquity
    # doesn't. Human-confirmed (see AGENTS.md milestone 3 log).
    "minority_interest": [
        "MinorityInterest",
    ],
    "temporary_equity": [
        "TemporaryEquityCarryingAmountAttributableToParent",
    ],
}

# Unit to read for each field; USD unless noted.
FIELD_UNIT: dict[str, str] = {
    "eps_basic": "USD/shares",
    "eps_diluted": "USD/shares",
    "shares_diluted": "shares",
}

# Fields where "no data" legitimately means zero (most companies have no noncontrolling
# interest / mezzanine equity) rather than a missing-data problem worth logging loudly.
ZERO_DEFAULT_FIELDS: frozenset[str] = frozenset({"minority_interest", "temporary_equity"})
