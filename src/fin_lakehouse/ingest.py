"""End-to-end ingestion: ticker -> CIK -> bronze landing. CLI entry for `make ingest`."""

from __future__ import annotations

import sys

import structlog

from fin_lakehouse.bronze.land import land_company_facts
from fin_lakehouse.edgar.cik import parse_ticker_map, resolve_cik
from fin_lakehouse.edgar.client import EdgarClient

logger = structlog.get_logger()


def ingest_ticker(ticker: str) -> None:
    with EdgarClient() as client:
        ticker_map = parse_ticker_map(client.fetch_ticker_map())
        cik10 = resolve_cik(ticker, ticker_map)
        facts = client.fetch_company_facts(cik10)
    path = land_company_facts(cik10, facts)
    logger.info("ingest.landed", ticker=ticker, cik=cik10, path=str(path))


def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "KHC"
    ingest_ticker(ticker)


if __name__ == "__main__":
    main()
