"""Ticker -> CIK resolution against SEC's company_tickers.json map (§5)."""

from __future__ import annotations

import json


class UnknownTickerError(KeyError):
    """Raised when a ticker is not present in the SEC ticker map."""


def parse_ticker_map(raw: bytes) -> dict[str, int]:
    """Parse company_tickers.json into {TICKER: cik} (unpadded int CIK)."""
    payload: dict[str, dict[str, object]] = json.loads(raw)
    return {
        str(entry["ticker"]).upper(): int(str(entry["cik_str"])) for entry in payload.values()
    }


def resolve_cik(ticker: str, ticker_map: dict[str, int]) -> str:
    """Resolve a ticker to its zero-padded 10-digit CIK string."""
    try:
        cik = ticker_map[ticker.upper()]
    except KeyError as exc:
        raise UnknownTickerError(f"ticker {ticker!r} not found in SEC ticker map") from exc
    return f"{cik:010d}"
