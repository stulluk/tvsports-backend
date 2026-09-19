"""Fetch Sahadan TV-programme JSON for the next few Istanbul days."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

ISTANBUL = ZoneInfo("Europe/Istanbul")
SAHADAN_TV_PROGRAM = "https://www.sahadan.com/api/index/tv-program"
USER_AGENT = "tvsports-backend/0.1 (+https://github.com/stulluk/tvsports-backend)"
DEFAULT_HORIZON_DAYS = 5
REQUEST_PAUSE_SECONDS = 0.4


def day_window(now: datetime, offset_days: int) -> tuple[datetime, datetime, datetime]:
    """Return Sahadan's [yesterday 21:00, day 20:59] window for one tab.

    The public TV page builds five tabs this way (see Sahadan tv-program chunk).
    ``now`` must be timezone-aware; naive values are treated as Istanbul.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=ISTANBUL)
    else:
        now = now.astimezone(ISTANBUL)
    day = (now + timedelta(days=offset_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = (day - timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
    end = day.replace(hour=20, minute=59, second=0, microsecond=0)
    return start, end, day


def _query(start: datetime, end: datetime) -> dict[str, str]:
    """Build the query string Sahadan's Nuxt client sends."""
    return {
        "a": "bs",
        "e": "bsbm",
        "u": start.strftime("%Y%m%d%H%M%S"),
        "application": "mackolik.com",
        "language": "tr",
        "country": "tr",
        "start_date": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "end_date": end.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def fetch_window(start: datetime, end: datetime, timeout: float = 30.0) -> dict[str, Any]:
    """GET one Sahadan TV-program window as parsed JSON."""
    url = f"{SAHADAN_TV_PROGRAM}?{urllib.parse.urlencode(_query(start, end))}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://www.sahadan.com/tv-programi",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Sahadan HTTP {exc.code} for {url}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Sahadan network error for {url}: {exc}") from exc
    return payload


def broadcasts_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the broadcasts list from a Sahadan tv-program payload."""
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return []
    items = data.get("broadcasts") or []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def fetch_horizon(
    now: datetime | None = None,
    days: int = DEFAULT_HORIZON_DAYS,
) -> list[dict[str, Any]]:
    """Fetch and merge broadcasts for ``days`` successive Istanbul tabs."""
    clock = now or datetime.now(ISTANBUL)
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offset in range(days):
        start, end, _day = day_window(clock, offset)
        payload = fetch_window(start, end)
        for item in broadcasts_from_payload(payload):
            match = item.get("match") or {}
            key = str(match.get("uuid") or match.get("mid") or item.get("date_time_utc"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        if offset + 1 < days:
            time.sleep(REQUEST_PAUSE_SECONDS)
    return merged
