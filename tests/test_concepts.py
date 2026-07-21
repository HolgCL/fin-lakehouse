from fin_lakehouse.edgar.concepts import CONCEPT_PRIORITY


def test_every_field_has_at_least_one_candidate_tag() -> None:
    for field, tags in CONCEPT_PRIORITY.items():
        assert len(tags) >= 1, f"{field} has no candidate tags"


def test_confirmed_fallback_tags_are_appended_after_spec_tags() -> None:
    # Human-confirmed additions (AGENTS.md milestone 2 log) must come after the brief's
    # originally-listed spec tags, never replace or reorder them.
    assert CONCEPT_PRIORITY["revenue"][:3] == [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ]
    assert CONCEPT_PRIORITY["revenue"][3:] == [
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
    ]
    assert CONCEPT_PRIORITY["payables"] == ["AccountsPayableCurrent", "AccountsPayableTradeCurrent"]
    assert CONCEPT_PRIORITY["long_term_debt"] == [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
    ]
