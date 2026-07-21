"""Per-rule tests against hand-built synthetic rows (docs/PROJECT_BRIEF.md §7) -- independent
of any real company data, verifying rule mechanics: does each rule fire exactly when its
condition holds, and not otherwise, and does it stay silent (not fired, no error) when the
data it needs is missing.
"""

from fin_lakehouse.detector.rules import RULE_CATALOGUE

_RULES = {rule.rule_id: rule for rule in RULE_CATALOGUE}


def test_catalogue_has_all_ten_rules_from_brief() -> None:
    assert set(_RULES) == {
        "negative_working_cap",
        "equity_wiped_by_gw",
        "goodwill_heavy",
        "revenue_quality",
        "ccc_deterioration",
        "leverage",
        "low_liquidity",
        "margin_erosion",
        "goodwill_impairment",
        "real_revenue_decline",
    }


def test_negative_working_cap_fires_below_zero() -> None:
    rule = _RULES["negative_working_cap"]
    fired = rule.evaluate({"working_capital": -1.0})
    not_fired = rule.evaluate({"working_capital": 0.0})
    assert fired.fired and fired.severity == "high"
    assert "negative" in fired.explanation
    assert not not_fired.fired
    assert not_fired.explanation is None


def test_equity_wiped_by_gw_fires_below_zero() -> None:
    rule = _RULES["equity_wiped_by_gw"]
    assert rule.evaluate({"equity_ex_goodwill": -1.0}).fired
    assert not rule.evaluate({"equity_ex_goodwill": 0.0}).fired


def test_goodwill_heavy_fires_above_threshold() -> None:
    rule = _RULES["goodwill_heavy"]
    fired = rule.evaluate({"goodwill_to_assets": 0.31})
    boundary = rule.evaluate({"goodwill_to_assets": 0.30})
    assert fired.fired
    assert "30%" in fired.explanation
    assert not boundary.fired  # strictly greater-than, not >=


def test_goodwill_heavy_threshold_is_configurable() -> None:
    rule = _RULES["goodwill_heavy"]
    result = rule.evaluate({"goodwill_to_assets": 0.25}, {"goodwill_to_assets_max": 0.20})
    assert result.fired


def test_revenue_quality_fires_only_when_both_conditions_hold() -> None:
    rule = _RULES["revenue_quality"]
    both = rule.evaluate({"dso_yoy": 0.23, "revenue_yoy": -0.04, "dso": 71.0})
    dso_only = rule.evaluate({"dso_yoy": 0.23, "revenue_yoy": 0.05, "dso": 71.0})
    revenue_only = rule.evaluate({"dso_yoy": 0.05, "revenue_yoy": -0.04, "dso": 60.0})
    assert both.fired
    assert "DSO rose +23%" in both.explanation
    assert "71 days" in both.explanation
    assert not dso_only.fired  # revenue grew, not a quality problem
    assert not revenue_only.fired  # DSO didn't rise enough


def test_ccc_deterioration_fires_above_threshold() -> None:
    rule = _RULES["ccc_deterioration"]
    assert rule.evaluate({"ccc_yoy": 0.21, "ccc": 50.0}).fired
    assert not rule.evaluate({"ccc_yoy": 0.19, "ccc": 50.0}).fired


def test_leverage_fires_only_when_both_conditions_hold() -> None:
    rule = _RULES["leverage"]
    both = rule.evaluate({"net_debt": 1.0, "debt_to_equity": 2.1})
    negative_net_debt = rule.evaluate({"net_debt": -1.0, "debt_to_equity": 3.0})
    low_d2e = rule.evaluate({"net_debt": 1.0, "debt_to_equity": 1.5})
    assert both.fired
    assert not negative_net_debt.fired
    assert not low_d2e.fired


def test_low_liquidity_fires_below_one() -> None:
    rule = _RULES["low_liquidity"]
    assert rule.evaluate({"current_ratio": 0.99}).fired
    assert not rule.evaluate({"current_ratio": 1.0}).fired


def test_margin_erosion_fires_below_negative_twenty_percent() -> None:
    rule = _RULES["margin_erosion"]
    fired = rule.evaluate({"net_margin_yoy": -0.21, "net_margin": 0.05})
    improvement = rule.evaluate({"net_margin_yoy": 1.20, "net_margin": 0.08})
    assert fired.fired
    assert not improvement.fired  # a recovery must never look like erosion


def test_goodwill_impairment_fires_when_positive() -> None:
    rule = _RULES["goodwill_impairment"]
    assert rule.evaluate({"goodwill_impairment": 1.0}).fired
    assert not rule.evaluate({"goodwill_impairment": 0.0}).fired


def test_real_revenue_decline_fires_only_when_nominal_up_real_down() -> None:
    rule = _RULES["real_revenue_decline"]
    fired = rule.evaluate({"revenue_real_yoy": -0.02, "revenue_yoy": 0.01})
    both_down = rule.evaluate({"revenue_real_yoy": -0.02, "revenue_yoy": -0.01})
    assert fired.fired
    assert not both_down.fired


def test_rule_with_missing_data_does_not_fire_and_has_no_error() -> None:
    for rule in RULE_CATALOGUE:
        result = rule.evaluate({field: None for field in rule.observed_fields})
        assert result.fired is False
        assert result.explanation is None


def test_real_revenue_decline_never_fires_without_a_cpi_table() -> None:
    """revenue_real_yoy doesn't exist in the gold table yet (§6 scope note) -- the rule must
    degrade to silently not-firing, not error, when the field is simply absent from the row."""
    rule = _RULES["real_revenue_decline"]
    result = rule.evaluate({"revenue_yoy": 0.05})  # no revenue_real_yoy key at all
    assert result.fired is False
