"""ingest_tickers orchestration tests against a mocked transport -- never the live SEC API."""

from pathlib import Path

import httpx
import pytest

from fin_lakehouse.config import Settings
from fin_lakehouse.edgar.client import COMPANY_FACTS_URL_TEMPLATE, TICKER_MAP_URL, EdgarClient
from fin_lakehouse.ingest import ingest_tickers

FIXTURES = Path(__file__).parent / "fixtures"
KHC_CIK10 = "0001637459"
AAPL_CIK10 = "0000320193"


def _client(call_log: list[str], cache_dir: Path) -> EdgarClient:
    def handler(request: httpx.Request) -> httpx.Response:
        call_log.append(str(request.url))
        url = str(request.url)
        if url == TICKER_MAP_URL:
            body = (FIXTURES / "company_tickers.json").read_bytes()
        elif url in (
            COMPANY_FACTS_URL_TEMPLATE.format(cik10=KHC_CIK10),
            COMPANY_FACTS_URL_TEMPLATE.format(cik10=AAPL_CIK10),
        ):
            body = (FIXTURES / "khc_companyfacts.json").read_bytes()  # content doesn't matter here
        else:
            raise AssertionError(f"unexpected request in test: {url}")
        return httpx.Response(200, content=body)

    return EdgarClient(
        settings=Settings(sec_user_agent="fin-lakehouse-test/0.1 (contact: test@example.com)"),
        cache_dir=cache_dir,
        client=httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": "test"}),
    )


def test_ingest_tickers_shares_one_client_across_the_universe(tmp_path: Path) -> None:
    call_log: list[str] = []
    client = _client(call_log, tmp_path / "cache")
    bronze_root = tmp_path / "bronze"

    ingest_tickers(["KHC", "AAPL"], client=client, bronze_root=bronze_root)
    client.close()

    # Ticker map fetched once (cached after that), not once per ticker.
    assert call_log.count(TICKER_MAP_URL) == 1
    assert (bronze_root / f"cik={KHC_CIK10}").exists()
    assert (bronze_root / f"cik={AAPL_CIK10}").exists()


def test_ingest_tickers_continues_past_unknown_ticker_and_raises_at_end(tmp_path: Path) -> None:
    call_log: list[str] = []
    client = _client(call_log, tmp_path / "cache")
    bronze_root = tmp_path / "bronze"

    with pytest.raises(RuntimeError, match="NOPE"):
        ingest_tickers(["KHC", "NOPE", "AAPL"], client=client, bronze_root=bronze_root)
    client.close()

    # The good tickers either side of the bad one still landed.
    assert (bronze_root / f"cik={KHC_CIK10}").exists()
    assert (bronze_root / f"cik={AAPL_CIK10}").exists()
