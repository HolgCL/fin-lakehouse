"""EdgarClient tests against a mocked transport — never the live SEC API."""

import json
from pathlib import Path

import httpx
import pytest

from fin_lakehouse.config import Settings
from fin_lakehouse.edgar.client import COMPANY_FACTS_URL_TEMPLATE, TICKER_MAP_URL, EdgarClient

FIXTURES = Path(__file__).parent / "fixtures"
KHC_CIK10 = "0001637459"


def _fixture_transport(call_log: list[str]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(str(request.url))
        if str(request.url) == TICKER_MAP_URL:
            body = (FIXTURES / "company_tickers.json").read_bytes()
        elif str(request.url) == COMPANY_FACTS_URL_TEMPLATE.format(cik10=KHC_CIK10):
            body = (FIXTURES / "khc_companyfacts.json").read_bytes()
        else:
            raise AssertionError(f"unexpected request in test: {request.url}")
        return httpx.Response(200, content=body)

    return httpx.MockTransport(handler)


def _client(tmp_path: Path, call_log: list[str]) -> EdgarClient:
    transport = _fixture_transport(call_log)
    return EdgarClient(
        settings=Settings(sec_user_agent="fin-lakehouse-test/0.1 (contact: test@example.com)"),
        cache_dir=tmp_path,
        client=httpx.Client(transport=transport, headers={"User-Agent": "test"}),
    )


def test_fetch_ticker_map_returns_fixture_bytes(tmp_path: Path) -> None:
    call_log: list[str] = []
    with _client(tmp_path, call_log) as client:
        raw = client.fetch_ticker_map()
    parsed = json.loads(raw)
    assert parsed["2"]["ticker"] == "KHC"


def test_fetch_company_facts_returns_fixture_bytes(tmp_path: Path) -> None:
    call_log: list[str] = []
    with _client(tmp_path, call_log) as client:
        raw = client.fetch_company_facts(KHC_CIK10)
    parsed = json.loads(raw)
    assert parsed["entityName"] == "Kraft Heinz Co"


def test_second_call_hits_cache_not_transport(tmp_path: Path) -> None:
    call_log: list[str] = []
    with _client(tmp_path, call_log) as client:
        client.fetch_ticker_map()
        client.fetch_ticker_map()
    assert call_log == [TICKER_MAP_URL]  # only the first call reached the transport


def test_retries_on_retryable_status_then_succeeds(tmp_path: Path) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, content=(FIXTURES / "company_tickers.json").read_bytes())

    client = EdgarClient(
        settings=Settings(sec_user_agent="fin-lakehouse-test/0.1 (contact: test@example.com)"),
        cache_dir=tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "test"}),
    )
    with client:
        raw = client.fetch_ticker_map()
    assert attempts["n"] == 3
    assert json.loads(raw)["2"]["ticker"] == "KHC"


def test_raises_on_non_retryable_status(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = EdgarClient(
        settings=Settings(sec_user_agent="fin-lakehouse-test/0.1 (contact: test@example.com)"),
        cache_dir=tmp_path,
        client=httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "test"}),
    )
    with client, pytest.raises(httpx.HTTPStatusError):
        client.fetch_ticker_map()
