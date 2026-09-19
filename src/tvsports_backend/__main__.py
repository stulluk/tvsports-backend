"""CLI: fetch Sahadan, filter, write JSON. Used by the container cron loop."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tvsports_backend.fetch_sahadan import DEFAULT_HORIZON_DAYS, fetch_horizon
from tvsports_backend.publish import build_document, write_document

ISTANBUL = ZoneInfo("Europe/Istanbul")


def refresh(output_dir: Path, horizon_days: int) -> Path:
    """Fetch, filter, and write a new schedule document."""
    raw = fetch_horizon(days=horizon_days)
    document = build_document(raw, horizon_days=horizon_days)
    path = write_document(document, output_dir)
    print(
        f"wrote {path} events={document['event_count']} "
        f"generated_at={document['generated_at']}",
        flush=True,
    )
    return path


def seconds_until_next_run(now: datetime, hours: tuple[int, ...] = (6, 18)) -> int:
    """Return seconds until the next 06:00 or 18:00 Europe/Istanbul slot."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=ISTANBUL)
    else:
        now = now.astimezone(ISTANBUL)
    candidates: list[datetime] = []
    for day_offset in (0, 1):
        day = (now + __import__("datetime").timedelta(days=day_offset)).date()
        for hour in hours:
            stamp = datetime(day.year, day.month, day.day, hour, 0, tzinfo=ISTANBUL)
            if stamp > now:
                candidates.append(stamp)
    wait = (min(candidates) - now).total_seconds()
    return max(1, int(wait))


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and run a one-shot refresh or the daily loop."""
    parser = argparse.ArgumentParser(description="TVsports Sahadan publisher")
    parser.add_argument(
        "--output-dir",
        default="/data",
        help="Directory for schedule.json and health.json",
    )
    parser.add_argument("--horizon-days", type=int, default=DEFAULT_HORIZON_DAYS)
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Refresh now, then again at 06:00 and 18:00 Europe/Istanbul",
    )
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)

    try:
        refresh(output_dir, args.horizon_days)
    except Exception as exc:  # noqa: BLE001 — container should keep serving last JSON
        print(f"refresh failed: {exc}", file=sys.stderr, flush=True)
        if not args.loop:
            return 1

    if not args.loop:
        return 0

    while True:
        wait = seconds_until_next_run(datetime.now(ISTANBUL))
        print(f"sleeping {wait}s until next 06:00/18:00 refresh", flush=True)
        time.sleep(wait)
        try:
            refresh(output_dir, args.horizon_days)
        except Exception as exc:  # noqa: BLE001
            print(f"refresh failed: {exc}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
