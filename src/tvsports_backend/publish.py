"""Write the public schedule JSON consumed by the Android app."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tvsports_backend import __version__
from tvsports_backend.filter_events import (
    ENTITY_BJK,
    ENTITY_F1,
    ENTITY_FENER_BASKETBALL,
    ENTITY_FENER_FOOTBALL,
    ENTITY_GS,
    ENTITY_REAL,
    ENTITY_TS,
    SAHADAN_NAIVE,
    filter_broadcasts,
    is_same_fixture,
)

ISTANBUL = ZoneInfo("Europe/Istanbul")
DEMO_DAY = date(2026, 9, 23)


def merge_events(
    primary: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep Sahadan rows on overlap; append later Spor Ekranı fixtures.

    Overlap is same Istanbul day, kickoff within 30 minutes, same sport, and
    club names that match after stripping SK/spor/Basket and expanding
    abbreviations (``Amed SK`` = ``Amedspor``, ``Atl. Madrid`` = ``Atletico``).
    Home/away order is ignored.
    """
    merged = list(primary)
    for item in extra:
        if any(is_same_fixture(item, existing) for existing in merged):
            continue
        merged.append(item)
    merged.sort(key=lambda row: (row.get("starts_at_utc") or "", row.get("title") or ""))
    return merged


def dense_day_demo_events(day: date = DEMO_DAY) -> list[dict[str, Any]]:
    """Seven same-day events, one color each, so the calendar overflow is visible."""
    specs = (
        (15, 0, "[DEMO] Fenerbahçe - Demo A", "Fenerbahçe", "Demo A", "Futbol", 1, ENTITY_FENER_FOOTBALL),
        (16, 0, "[DEMO] Fenerbahçe Tarfin - Demo B", "Fenerbahçe Tarfin", "Demo B", "Basketbol", 2, ENTITY_FENER_BASKETBALL),
        (17, 0, "[DEMO] Galatasaray - Demo C", "Galatasaray", "Demo C", "Futbol", 1, ENTITY_GS),
        (18, 0, "[DEMO] Beşiktaş - Demo D", "Beşiktaş", "Demo D", "Futbol", 1, ENTITY_BJK),
        (19, 0, "[DEMO] Trabzonspor - Demo E", "Trabzonspor", "Demo E", "Futbol", 1, ENTITY_TS),
        (20, 0, "[DEMO] Real Madrid - Demo F", "Real Madrid", "Demo F", "Futbol", 1, ENTITY_REAL),
        (21, 0, "[DEMO] Formula 1 - Demo GP", "Formula 1", "Demo GP", "Formula 1", 99, ENTITY_F1),
    )
    events: list[dict[str, Any]] = []
    for hour, minute, title, home, away, sport, sport_id, entity in specs:
        istanbul = datetime.combine(day, time(hour, minute), tzinfo=ISTANBUL)
        utc = istanbul.astimezone(ZoneInfo("UTC"))
        events.append(
            {
                "id": f"demo-dense-{entity}",
                "source_match_id": None,
                "starts_at_utc": utc.strftime(SAHADAN_NAIVE),
                "starts_at_istanbul": istanbul.strftime(SAHADAN_NAIVE),
                "title": title,
                "home": home,
                "away": away,
                "sport": sport,
                "sport_id": sport_id,
                "channels": ["Demo TV"],
                "entity_ids": [entity],
                "source": "mock",
            }
        )
    return events


def _horizon_days(events: list[dict[str, Any]], fallback: int) -> int:
    """Span from today (Istanbul) to the last event date, at least fallback."""
    last: date | None = None
    for event in events:
        stamp = str(event.get("starts_at_istanbul") or "")[:10]
        try:
            parsed = date.fromisoformat(stamp)
        except ValueError:
            continue
        if last is None or parsed > last:
            last = parsed
    if last is None:
        return fallback
    today = datetime.now(ISTANBUL).date()
    return max(fallback, (last - today).days + 1)


def build_document(
    raw_broadcasts: list[dict[str, Any]],
    generated_at: datetime | None = None,
    horizon_days: int = 5,
    sporekrani_raw: list[dict[str, Any]] | None = None,
    include_demo: bool = False,
) -> dict[str, Any]:
    """Build the public JSON document from Sahadan and optional Spor Ekranı rows."""
    stamp = generated_at or datetime.now(ISTANBUL)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ISTANBUL)
    sahadan_events = filter_broadcasts(raw_broadcasts)
    extra_events = filter_broadcasts(sporekrani_raw or [])
    events = merge_events(sahadan_events, extra_events)
    sources = ["sahadan"]
    if sporekrani_raw:
        sources.append("sporekrani")
    if include_demo:
        events = merge_events(events, dense_day_demo_events())
        sources.append("mock")
    span = _horizon_days(events, horizon_days)
    return {
        "schema": "tvsports.schedule.v1",
        "generated_at": stamp.isoformat(),
        "source": "+".join(sources),
        "source_url": "https://www.sahadan.com/tv-programi",
        "extra_source_url": "https://www.sporekrani.com" if sporekrani_raw else None,
        "horizon_days": span,
        "backend_version": __version__,
        "event_count": len(events),
        "events": events,
        "note": (
            "starts_at_utc is UTC. starts_at_istanbul is Europe/Istanbul. "
            "Sahadan wins on the same-day overlap; Spor Ekranı fills later dates. "
            "Rows with source=mock are a calendar overflow demo and are not real fixtures."
        ),
    }


def write_document(document: dict[str, Any], output_dir: Path) -> Path:
    """Write schedule.json and a small health.json into output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    schedule_path = output_dir / "schedule.json"
    health_path = output_dir / "health.json"
    schedule_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    health = {
        "ok": True,
        "generated_at": document.get("generated_at"),
        "event_count": document.get("event_count"),
        "source": document.get("source"),
        "version": document.get("backend_version"),
        "horizon_days": document.get("horizon_days"),
    }
    health_path.write_text(
        json.dumps(health, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return schedule_path
