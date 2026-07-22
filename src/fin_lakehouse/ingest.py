"""End-to-end ingestion: ticker(s) -> CIK -> bronze landing. CLI entry for `make ingest`.

Ingesting a whole universe uses a single shared EdgarClient so its rate limiter actually
governs the full run (a fresh client per ticker would reset the limiter's state each time).
"""

from __future__ import annotations

import sys
from pathlib import Path

import structlog

from fin_lakehouse.bronze.land import BRONZE_ROOT, land_company_facts
from fin_lakehouse.edgar.cik import parse_ticker_map, resolve_cik
from fin_lakehouse.edgar.client import EdgarClient
from fin_lakehouse.universe import UNIVERSE

logger = structlog.get_logger()


def ingest_tickers(
    tickers: list[str],
    client: EdgarClient | None = None,
    bronze_root: Path = BRONZE_ROOT,
) -> None:
    failures: list[str] = []
    owns_client = client is None
    client = client or EdgarClient()
    try:
        ticker_map = parse_ticker_map(client.fetch_ticker_map())
        for ticker in tickers:
            try:
                cik10 = resolve_cik(ticker, ticker_map)
                facts = client.fetch_company_facts(cik10)
            except Exception:
                logger.exception("ingest.failed", ticker=ticker)
                failures.append(ticker)
                continue
            path = land_company_facts(cik10, facts, bronze_root=bronze_root)
            logger.info("ingest.landed", ticker=ticker, cik=cik10, path=str(path))
    finally:
        if owns_client:
            client.close()
    if failures:
        raise RuntimeError(f"failed to ingest {len(failures)} ticker(s): {failures}")


def ingest_ticker(ticker: str) -> None:
    ingest_tickers([ticker])


def main() -> None:
    tickers = sys.argv[1:] if len(sys.argv) > 1 else UNIVERSE
    ingest_tickers(tickers)


if __name__ == "__main__":
    main()
