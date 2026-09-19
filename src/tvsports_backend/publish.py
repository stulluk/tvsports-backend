"""Write the public schedule JSON consumed by the Android app."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tvsports_backend import __version__
from tvsports_backend.filter_events import filter_broadcasts

ISTANBUL = ZoneInfo("Europe/Istanbul")


def build_document(
    raw_broadcasts: list[dict[str, Any]],
    generated_at: datetime | None = None,
    horizon_days: int = 5,
) -> dict[str, Any]:
    """Build the public JSON document from raw Sahadan broadcasts."""
    stamp = generated_at or datetime.now(ISTANBUL)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=ISTANBUL)
    events = filter_broadcasts(raw_broadcasts)
    return {
        "schema": "tvsports.schedule.v1",
        "generated_at": stamp.isoformat(),
        "source": "sahadan",
        "source_url": "https://www.sahadan.com/tv-programi",
        "horizon_days": horizon_days,
        "backend_version": __version__,
        "event_count": len(events),
        "events": events,
        "note": (
            "starts_at_utc is Sahadan's date_time_utc field, shown as-is on "
            "their TV page (treated as the kickoff they publish, not converted)."
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
    }
    health_path.write_text(
        json.dumps(health, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return schedule_path
