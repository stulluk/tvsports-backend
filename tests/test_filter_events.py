"""Filter tests against a captured Sahadan payload from 2026-09-19."""

from __future__ import annotations

import json
from pathlib import Path

from tvsports_backend.filter_events import classify_entities, filter_broadcasts

FIXTURE = Path(__file__).parent / "fixtures" / "sahadan_sample.json"


def _titles(events: list[dict]) -> list[str]:
    return [item["title"] for item in events]


def test_keeps_followed_football_and_fener_basketball() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    events = filter_broadcasts(raw)
    titles = _titles(events)
    assert "Trabzonspor - Galatasaray" in titles
    assert "Fenerbahçe - Eyüpspor" in titles
    assert "Sevilla - Barcelona" in titles
    assert "Atl. Madrid - Real Madrid" in titles
    assert "Amed SK - Beşiktaş" in titles
    assert "Fenerbahçe Tarfin - Dubai" in titles
    assert "Fenerbahçe Tarfin - Beşiktaş" in titles


def test_drops_women_youth_other_branches_and_f4() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    titles = _titles(filter_broadcasts(raw))
    assert "Beşiktaş (K) - Fenerbahçe (K)" not in titles
    assert "Fomget Gençlik (K) - Trabzonspor (K)" not in titles
    assert "Tofaş - Galatasaray MCT T." not in titles
    assert "Olympiakos - Real Madrid" not in titles
    assert not any("Formula 4" in title for title in titles)


def test_derby_is_tagged_for_both_clubs() -> None:
    entities = classify_entities("Trabzonspor - Galatasaray", 1, "Futbol")
    assert entities == ["trabzonspor", "galatasaray"]


def test_f1_keeps_quali_drops_practice() -> None:
    assert classify_entities("Formula 1 - Sıralama Turları", 99, "Formula 1") == [
        "formula1"
    ]
    assert classify_entities("Formula 1 - Sprint Yarışı", 99, "Formula 1") == [
        "formula1"
    ]
    assert classify_entities("Formula 1 - Antrenman Turları-1", 99, "Formula 1") == []
    assert classify_entities("İtalya Formula 4 - Yarış 1", 10, "WRC") == []
