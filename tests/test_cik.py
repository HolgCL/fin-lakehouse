"""CIK resolution tests against a saved, real (trimmed) fixture of company_tickers.json."""

import json
from pathlib import Path

import pytest

from fin_lakehouse.edgar.cik import UnknownTickerError, parse_ticker_map, resolve_cik

FIXTURE = Path(__file__).parent / "fixtures" / "company_tickers.json"


def test_parse_ticker_map_from_fixture() -> None:
    ticker_map = parse_ticker_map(FIXTURE.read_bytes())
    assert ticker_map["KHC"] == 1637459
    assert ticker_map["AAPL"] == 320193


def test_resolve_cik_zero_pads_to_ten_digits() -> None:
    ticker_map = parse_ticker_map(FIXTURE.read_bytes())
    assert resolve_cik("KHC", ticker_map) == "0001637459"


def test_resolve_cik_is_case_insensitive() -> None:
    ticker_map = parse_ticker_map(FIXTURE.read_bytes())
    assert resolve_cik("khc", ticker_map) == "0001637459"


def test_resolve_cik_unknown_ticker_raises() -> None:
    ticker_map = parse_ticker_map(FIXTURE.read_bytes())
    with pytest.raises(UnknownTickerError):
        resolve_cik("NOPE", ticker_map)


def test_parse_ticker_map_matches_independent_json_read() -> None:
    """Oracle computed independently of parse_ticker_map, straight from the raw JSON."""
    raw = json.loads(FIXTURE.read_bytes())
    expected = {entry["ticker"]: entry["cik_str"] for entry in raw.values()}
    ticker_map = parse_ticker_map(FIXTURE.read_bytes())
    assert ticker_map == expected
