"""Fetch Spor Ekranı team / F1 pages and turn JSON-LD into Sahadan-shaped rows."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from tvsports_backend.filter_events import (
    F1_DROP,
    F1_KEEP,
    SAHADAN_NAIVE,
    _norm,
    _sides,
)

ISTANBUL = ZoneInfo("Europe/Istanbul")
USER_AGENT = "tvsports-backend/0.2 (+https://github.com/stulluk/tvsports-backend)"
REQUEST_PAUSE_SECONDS = 0.4
ORIGIN = "https://www.sporekrani.com"

TEAM_PAGES = (
    f"{ORIGIN}/home/team/fenerbahce",
    f"{ORIGIN}/home/team/galatasaray",
    f"{ORIGIN}/home/team/besiktas",
    f"{ORIGIN}/home/team/trabzonspor",
    f"{ORIGIN}/home/team/real-madrid",
    f"{ORIGIN}/home/team/barcelona",
)
F1_LEAGUE_PAGE = f"{ORIGIN}/home/league/formula-1"
MATCH_PATH_RE = re.compile(
    r"/home/match/\d+/\d{4}/\d{2}/\d{2}/[^\"'\s>]+",
)
LD_SCRIPT_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
    re.S,
)
LIVE_SUFFIX = re.compile(r"\s+canlı yayın\s*$", re.IGNORECASE)

BASKET_MARK = re.compile(
    r"basketbol|euroleague|tarfin|\bbasket\b",
    re.IGNORECASE,
)
OTHER_SPORT_MARK = re.compile(
    r"hentbol|voleybol|\btenis\b",
    re.IGNORECASE,
)


def fetch_html(url: str, timeout: float = 30.0) -> str:
    """GET a Spor Ekranı HTML page."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html",
            "Referer": f"{ORIGIN}/",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Spor Ekranı HTTP {exc.code} for {url}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Spor Ekranı network error for {url}: {exc}") from exc


def _ld_blocks(html: str) -> list[Any]:
    """Parse every application/ld+json script into Python values."""
    blocks: list[Any] = []
    for match in LD_SCRIPT_RE.finditer(html):
        try:
            blocks.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
    return blocks


def _graph_items(html: str) -> list[dict[str, Any]]:
    """Flatten @graph / list / single-object JSON-LD into dicts."""
    items: list[dict[str, Any]] = []
    for block in _ld_blocks(html):
        if isinstance(block, list):
            candidates = block
        elif isinstance(block, dict) and isinstance(block.get("@graph"), list):
            candidates = block["@graph"]
        elif isinstance(block, dict):
            candidates = [block]
        else:
            continue
        for item in candidates:
            if isinstance(item, dict):
                items.append(item)
    return items


def _services_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index BroadcastService nodes so @id-only publishedOn can be resolved."""
    services: dict[str, dict[str, Any]] = {}
    for item in items:
        if item.get("@type") == "BroadcastService" and item.get("@id"):
            services[str(item["@id"])] = item
    return services


def _channel_names(published: Any, services: dict[str, dict[str, Any]]) -> list[str]:
    """Collect display names and drop the placeholder 'Yayın Yok'."""
    rows = published if isinstance(published, list) else ([published] if published else [])
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("broadcastDisplayName")
        if not name and row.get("@id") in services:
            name = services[str(row["@id"])].get("name")
        if not name:
            continue
        if _norm(str(name)) in {"yayin yok", "yayın yok"}:
            continue
        if name not in names:
            names.append(str(name))
    return names


def infer_sport(name: str, url: str) -> tuple[int, str]:
    """Guess Sahadan sport id / name from a Spor Ekranı title and URL."""
    blob = f"{name} {url}"
    if re.search(r"formula[\s-]*1|\bf1\b", blob, re.IGNORECASE):
        return 99, "Formula 1"
    if BASKET_MARK.search(blob):
        return 2, "Basketbol"
    if OTHER_SPORT_MARK.search(blob):
        return 0, "Other"
    return 1, "Futbol"


def _clean_title(name: str) -> str:
    """Strip the trailing 'canlı yayın' suffix Spor Ekranı adds on team pages."""
    return LIVE_SUFFIX.sub("", name).strip()


def _match_id(url: str) -> str | None:
    """Return the numeric match id embedded in a Spor Ekranı URL."""
    match = re.search(r"/home/match/(\d+)/", url)
    return match.group(1) if match else None


def _start_to_utc_naive(start_date: str) -> str | None:
    """Convert an ISO-8601 startDate (usually +03:00) to naive UTC."""
    try:
        stamp = datetime.fromisoformat(start_date)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ISTANBUL)
    return stamp.astimezone(timezone.utc).strftime(SAHADAN_NAIVE)


def _broadcasts_from_items(
    items: list[dict[str, Any]],
    page_url: str,
) -> list[dict[str, Any]]:
    """Build Sahadan-shaped rows from JSON-LD BroadcastEvent nodes."""
    services = _services_by_id(items)
    sports_by_id = {
        str(item.get("@id")): item
        for item in items
        if item.get("@type") == "SportsEvent" and item.get("@id")
    }
    rows: list[dict[str, Any]] = []
    for item in items:
        if item.get("@type") != "BroadcastEvent":
            continue
        url = str(item.get("url") or page_url)
        start = item.get("startDate")
        title = _clean_title(str(item.get("name") or ""))
        broadcast_of = item.get("broadcastOfEvent") or {}
        event_id = ""
        if isinstance(broadcast_of, dict):
            event_id = str(broadcast_of.get("@id") or "")
        sports = sports_by_id.get(event_id, {})
        if sports.get("name"):
            sports_name = str(sports["name"])
            if re.search(r"formula[\s-]*1|\bf1\b", url, re.IGNORECASE):
                title = f"Formula 1 - {sports_name}"
            elif not title:
                title = sports_name
        if not start or not title:
            continue
        utc = _start_to_utc_naive(str(start))
        if not utc:
            continue
        sport, sport_name = infer_sport(title, url)
        mid = _match_id(url) or title
        home, away = _sides(title)
        rows.append(
            {
                "date_time_utc": utc,
                "match": {
                    "id": mid,
                    "uuid": f"se-{mid}",
                    "sport": sport,
                    "name": title,
                    "sport_name": sport_name,
                },
                "channels": [{"name": name} for name in _channel_names(item.get("publishedOn"), services)],
                "source_url": url,
                "source": "sporekrani",
                "home_hint": home,
                "away_hint": away,
            }
        )
    return rows


def broadcasts_from_html(html: str, page_url: str) -> list[dict[str, Any]]:
    """Parse one Spor Ekranı HTML page into Sahadan-shaped broadcasts."""
    return _broadcasts_from_items(_graph_items(html), page_url)


def f1_match_urls(html: str) -> list[str]:
    """Collect F1 quali / sprint / race match URLs from the league page."""
    found: list[str] = []
    seen: set[str] = set()
    for path in MATCH_PATH_RE.findall(html):
        slug = path.rsplit("/", 1)[-1].replace("-", " ")
        if F1_DROP.search(slug):
            continue
        if not F1_KEEP.search(slug):
            continue
        url = ORIGIN + path
        if url in seen:
            continue
        seen.add(url)
        found.append(url)
    return found


def fetch_horizon(pause: float = REQUEST_PAUSE_SECONDS) -> list[dict[str, Any]]:
    """Fetch team pages plus dated F1 match pages and merge unique rows."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_rows(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            key = str((row.get("match") or {}).get("uuid") or row.get("source_url"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

    pages = list(TEAM_PAGES) + [F1_LEAGUE_PAGE]
    league_html = ""
    for index, url in enumerate(pages):
        html = fetch_html(url)
        if url == F1_LEAGUE_PAGE:
            league_html = html
        add_rows(broadcasts_from_html(html, url))
        if index + 1 < len(pages):
            time.sleep(pause)

    match_urls = f1_match_urls(league_html) if league_html else []
    for index, url in enumerate(match_urls):
        html = fetch_html(url)
        add_rows(broadcasts_from_html(html, url))
        if index + 1 < len(match_urls):
            time.sleep(pause)
    return merged
