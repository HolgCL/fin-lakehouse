"""Silver normalization: tag-priority extraction into a tidy company-year table.

Dedup rule for facts sharing (concept, fiscal_year), human-confirmed (see AGENTS.md milestone 2
log): the entry with the latest `end` date wins (discards same-filing prior-year comparatives —
SEC's companyfacts payload tags both the current and prior period-end with the same fy/fp/form
inside one 10-K); ties are broken by latest `filed` (captures restatements). A remaining value
conflict is logged loudly, never silently resolved.

Duration facts (income-statement concepts, identified by having a `start`) are additionally
required to span a full fiscal year (~350-380 days) before dedup runs. Without this, a single
10-K's Q4-only duration fact can share the exact `end` date with the true annual figure and get
mistaken for a "conflicting" duplicate of it — human-confirmed fix, see AGENTS.md milestone 2 log.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import polars as pl
import structlog

from fin_lakehouse.edgar.concepts import CONCEPT_PRIORITY, FIELD_UNIT, ZERO_DEFAULT_FIELDS

logger = structlog.get_logger()

ANNUAL_FORM = "10-K"
ANNUAL_FP = "FY"
_MIN_ANNUAL_SPAN_DAYS = 350
_MAX_ANNUAL_SPAN_DAYS = 380


def _is_annual_span(entry: dict[str, Any]) -> bool:
    """True for instant facts (no `start`) or duration facts spanning a full fiscal year."""
    start = entry.get("start")
    if start is None:
        return True
    span = (dt.date.fromisoformat(entry["end"]) - dt.date.fromisoformat(start)).days
    return _MIN_ANNUAL_SPAN_DAYS <= span <= _MAX_ANNUAL_SPAN_DAYS


def _annual_facts(raw_facts: dict[str, Any], tag: str, unit: str) -> list[dict[str, Any]]:
    concept = raw_facts.get(tag)
    if concept is None:
        return []
    entries: list[dict[str, Any]] = concept.get("units", {}).get(unit, [])
    return [
        e
        for e in entries
        if e.get("form") == ANNUAL_FORM and e.get("fp") == ANNUAL_FP and _is_annual_span(e)
    ]


def _pick_fact(entries: list[dict[str, Any]], tag: str, fiscal_year: int) -> float:
    max_end = max(e["end"] for e in entries)
    candidates = [e for e in entries if e["end"] == max_end]
    if len(candidates) > 1:
        max_filed = max(e["filed"] for e in candidates)
        candidates = [e for e in candidates if e["filed"] == max_filed]
    if len(candidates) > 1:
        # Rare tagging oddity: a concept normally reported as a duration also has an
        # instant-tagged fact (no `start`) sharing the same end/filed. Prefer the genuine
        # duration fact as the more specific representation of a period figure.
        with_start = [c for c in candidates if c.get("start") is not None]
        if with_start:
            candidates = with_start
    values = {c["val"] for c in candidates}
    if len(values) > 1:
        logger.warning(
            "silver.fact_conflict",
            tag=tag,
            fiscal_year=fiscal_year,
            end=max_end,
            candidates=[
                {"val": c["val"], "filed": c["filed"], "accn": c["accn"]} for c in candidates
            ],
        )
    return float(candidates[0]["val"])


def _extract_field(
    raw_facts: dict[str, Any], field: str, fiscal_year: int
) -> tuple[float | None, str | None]:
    unit = FIELD_UNIT.get(field, "USD")
    for tag in CONCEPT_PRIORITY[field]:
        entries = [e for e in _annual_facts(raw_facts, tag, unit) if e.get("fy") == fiscal_year]
        if entries:
            return _pick_fact(entries, tag, fiscal_year), tag
    return None, None


def _fiscal_years(raw_facts: dict[str, Any]) -> list[int]:
    years: set[int] = set()
    for field, tags in CONCEPT_PRIORITY.items():
        unit = FIELD_UNIT.get(field, "USD")
        for tag in tags:
            for entry in _annual_facts(raw_facts, tag, unit):
                if entry.get("fy") is not None:
                    years.add(int(entry["fy"]))
    return sorted(years)


_SCHEMA: dict[str, pl.DataType] = {
    "cik": pl.Utf8(),
    "entity_name": pl.Utf8(),
    "fiscal_year": pl.Int64(),
    **{field: pl.Float64() for field in CONCEPT_PRIORITY},
}


def extract_company_year(cik10: str, entity_name: str, raw_companyfacts: bytes) -> pl.DataFrame:
    """Tag-priority extraction into one row per fiscal year, §5 fields as columns.

    Missing fields are left null and logged loudly (never coerced to 0), per §1.6. An explicit
    schema keeps dtypes consistent even when a company has an entirely-null field -- polars would
    otherwise infer that column as Null instead of Float64, which then conflicts when
    concatenating that company with others that do have data for it (see AGENTS.md milestone 5
    log).
    """
    payload = json.loads(raw_companyfacts)
    raw_facts: dict[str, Any] = payload.get("facts", {}).get("us-gaap", {})

    rows: list[dict[str, Any]] = []
    for fiscal_year in _fiscal_years(raw_facts):
        row: dict[str, Any] = {
            "cik": cik10,
            "entity_name": entity_name,
            "fiscal_year": fiscal_year,
        }
        for field in CONCEPT_PRIORITY:
            value, _tag_used = _extract_field(raw_facts, field, fiscal_year)
            if value is None and field in ZERO_DEFAULT_FIELDS:
                value = 0.0  # no data legitimately means zero for these (see concepts.py)
            elif value is None:
                logger.warning(
                    "silver.missing_field",
                    cik=cik10,
                    entity_name=entity_name,
                    fiscal_year=fiscal_year,
                    field=field,
                )
            row[field] = value
        rows.append(row)

    return pl.DataFrame(rows, schema=_SCHEMA)
