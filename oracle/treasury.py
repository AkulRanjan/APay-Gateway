from __future__ import annotations

from datetime import date, datetime, timezone
from xml.etree import ElementTree

import httpx

import config
from models import Observation
from oracle.cache import TTLCache
from oracle.tenors import TENOR_FIELDS

# Treasury's officially documented, daily-updated XML feed. It is intentionally
# isolated here so a Fiscal Data JSON client can replace it without touching the
# scoring engine or gateway.
TREASURY_YIELD_URL = "https://home.treasury.gov/sites/default/files/interest-rates/yield.xml"


class UnsupportedTenor(ValueError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_date(value: str) -> date | None:
    value = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def parse_yield_curve(xml: str, field_name: str) -> tuple[date, float] | None:
    """Extract the most recent non-empty tenor value from Treasury Atom XML."""
    root = ElementTree.fromstring(xml)
    candidates: list[tuple[date, float]] = []
    for entry in root.iter():
        if _local_name(entry.tag) != "entry":
            continue
        values = {_local_name(node.tag): (node.text or "").strip() for node in entry.iter()}
        raw_date = values.get("NEW_DATE") or values.get("QUOTE_DATE") or values.get("record_date")
        raw_yield = values.get(field_name)
        if not raw_date or not raw_yield or raw_yield.upper() in {"N/A", "NA"}:
            continue
        parsed_date = _parse_date(raw_date)
        try:
            parsed_yield = float(raw_yield)
        except ValueError:
            parsed_yield = -1
        if parsed_date is not None and parsed_yield >= 0:
            candidates.append((parsed_date, parsed_yield))
    return max(candidates, default=None, key=lambda item: item[0])


class TreasuryOracle:
    def __init__(self, *, client: httpx.AsyncClient | None = None, url: str = TREASURY_YIELD_URL) -> None:
        self._client = client
        self._url = url
        self._cache: TTLCache[Observation] = TTLCache(config.ORACLE_CACHE_TTL_SECONDS)

    async def get_observation(self, tenor: str) -> Observation | None:
        field_name = TENOR_FIELDS.get(tenor)
        if field_name is None:
            raise UnsupportedTenor(tenor)
        cached = self._cache.get(tenor)
        if cached is not None:
            return cached.model_copy(update={"cache_hit": True})

        timeout = httpx.Timeout(config.ORACLE_TIMEOUT_SECONDS, connect=config.ORACLE_TIMEOUT_SECONDS)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
        try:
            # One retry only for transport failures. HTTP error responses do not retry.
            response = None
            for attempt in range(2):
                try:
                    response = await client.get(self._url)
                    break
                except httpx.TransportError:
                    if attempt:
                        return None
            if response is None or response.is_error:
                return None
            parsed = parse_yield_curve(response.text, field_name)
            if parsed is None:
                return None
            record_date, percent = parsed
            observation = Observation(
                source="home.treasury.gov", tenor=tenor,
                observed_yield_bps=int(round(percent * 100)), record_date=record_date,
                fetched_at=datetime.now(timezone.utc), cache_hit=False,
            )
            self._cache.set(tenor, observation)
            return observation
        except (httpx.HTTPError, ElementTree.ParseError):
            return None
        finally:
            if owns_client:
                await client.aclose()
