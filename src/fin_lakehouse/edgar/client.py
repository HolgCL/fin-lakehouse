"""SEC EDGAR HTTP client: UA header, retry with backoff+jitter, rate limiting, on-disk cache.

See docs/PROJECT_BRIEF.md §5 for the exact endpoint/rate-limit/caching spec this implements.
"""

from __future__ import annotations

import hashlib
import random
import time
from pathlib import Path
from types import TracebackType

import httpx
import structlog

from fin_lakehouse.config import Settings

logger = structlog.get_logger()

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL_TEMPLATE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

# Keeps us under the ~10 req/s limit from §5.
_MIN_REQUEST_INTERVAL_S = 0.11
_MAX_RETRIES = 5
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class EdgarClient:
    """Thin httpx wrapper enforcing SEC's UA/rate-limit rules with a verbatim on-disk cache."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache_dir: Path = Path("data/cache"),
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = client or httpx.Client(
            headers={"User-Agent": self._settings.sec_user_agent}, timeout=30.0
        )
        self._last_request_at = 0.0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> EdgarClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def fetch_ticker_map(self) -> bytes:
        """Raw bytes of the ticker->CIK map (§5)."""
        return self._get(TICKER_MAP_URL)

    def fetch_company_facts(self, cik10: str) -> bytes:
        """Raw bytes of the companyfacts payload for a zero-padded 10-digit CIK."""
        return self._get(COMPANY_FACTS_URL_TEMPLATE.format(cik10=cik10))

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode()).hexdigest()[:16]
        stem = url.rsplit("/", 1)[-1].removesuffix(".json")
        return self._cache_dir / f"{stem}-{digest}.json"

    def _get(self, url: str) -> bytes:
        cache_path = self._cache_path(url)
        if cache_path.exists():
            logger.debug("edgar.cache_hit", url=url, path=str(cache_path))
            return cache_path.read_bytes()

        content = self._request_with_retry(url)
        cache_path.write_bytes(content)
        return content

    def _request_with_retry(self, url: str) -> bytes:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            self._respect_rate_limit()
            try:
                response = self._client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES or exc.response.status_code not in _RETRYABLE_STATUSES:
                    raise
                self._backoff(attempt, url, exc)
                continue
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    raise
                self._backoff(attempt, url, exc)
                continue
            else:
                return response.content
        assert last_exc is not None
        raise last_exc

    def _backoff(self, attempt: int, url: str, exc: Exception) -> None:
        delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
        logger.warning(
            "edgar.retry", url=url, attempt=attempt, delay_s=round(delay, 2), error=str(exc)
        )
        time.sleep(delay)

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_REQUEST_INTERVAL_S:
            time.sleep(_MIN_REQUEST_INTERVAL_S - elapsed)
        self._last_request_at = time.monotonic()
