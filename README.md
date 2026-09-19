# TVsports backend

AGPL-3.0-or-later. Fetches the Sahadan TV programme, keeps only the
broadcasts TVsports follows, and serves a static JSON file.

The Android app reads this JSON. Default public hosts:

- primary: `https://tvsports.kernelmax.com/schedule.json` (dc6)
- backup: `https://tvsports2.kernelmax.com/schedule.json` (dc4)

Deploy credentials never belong in this repository. Put SSH keys in
GitHub Actions secrets if you add CI later.

## What is published

`schedule.json` is rebuilt on container start and again at 06:00 and
18:00 Europe/Istanbul. Sahadan covers the next five day-tabs (previous
day 21:00 through that day 20:59). Spor Ekranı team / F1 JSON-LD fills
later fixtures through roughly two months. On the same match, Sahadan
wins because its channel list is usually better. Club names are compared
after stripping SK/FK/Basket and a trailing ``spor``, so ``Amed SK`` and
``Amedspor`` (or ``Atl. Madrid`` / ``Atletico Madrid``) collapse to one
row without an AI step on the servers.

`TVSPORTS_INCLUDE_DEMO=1` can inject a seven-event mock day for calendar
overflow checks. It stays off in production.

Followed entities (filter is in `src/tvsports_backend/filter_events.py`):

- Fenerbahce men's football
- Fenerbahce basketball (all competitions)
- Galatasaray, Besiktas, Trabzonspor men's football only
- Real Madrid and Barcelona football (all competitions, friendlies included)
- Formula 1 qualifying, sprint, and race (no practice)

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[ ]' pytest
PYTHONPATH=src python -m tvsports_backend --output-dir ./data
```

Tests:

```bash
PYTHONPATH=src pytest
```

## Docker

```bash
docker compose build
TVSPORTS_HOSTNAME=tvsports.kernelmax.com docker compose up -d
```

On dc4, where port 80/443 are already used by ntfy Caddy:

```bash
docker compose -f docker-compose.yml -f docker-compose.dc4.yml up -d
```

Then point ntfy Caddy at `127.0.0.1:8088`.

## Change the public hostname

Set `TVSPORTS_HOSTNAME` in the environment. The Android app also has a
setting to point at any self-hosted copy of this JSON.
