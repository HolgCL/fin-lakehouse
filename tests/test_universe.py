from fin_lakehouse.universe import UNIVERSE


def test_universe_is_nonempty_and_around_twenty_tickers() -> None:
    assert 15 <= len(UNIVERSE) <= 25


def test_universe_tickers_are_unique_and_uppercase() -> None:
    assert len(UNIVERSE) == len(set(UNIVERSE))
    assert all(ticker == ticker.upper() for ticker in UNIVERSE)


def test_universe_includes_the_flagship_case_study() -> None:
    assert "KHC" in UNIVERSE
