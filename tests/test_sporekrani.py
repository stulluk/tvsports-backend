"""Spor Ekranı JSON-LD parse, filter, and merge tests."""

from __future__ import annotations

import json
from pathlib import Path

from tvsports_backend.fetch_sporekrani import (
    broadcasts_from_html,
    f1_match_urls,
    infer_sport,
)
from tvsports_backend.filter_events import classify_entities, filter_broadcasts
from tvsports_backend.publish import (
    build_document,
    dense_day_demo_events,
    merge_events,
)

FIXTURES = Path(__file__).parent / "fixtures"
TEAM_HTML = (FIXTURES / "sporekrani_team_snippet.html").read_text(encoding="utf-8")
F1_LEAGUE_HTML = (FIXTURES / "sporekrani_f1_league_snippet.html").read_text(encoding="utf-8")
F1_MATCH_HTML = (FIXTURES / "sporekrani_f1_match_snippet.html").read_text(encoding="utf-8")
SAHADAN = json.loads((FIXTURES / "sahadan_sample.json").read_text(encoding="utf-8"))


def test_infer_sport_from_url() -> None:
    assert infer_sport("Fenerbahçe - Eyüpspor", "trendyol-super-lig") == (1, "Futbol")
    assert infer_sport("Fenerbahçe Tarfin - Bayern", "euroleague") == (2, "Basketbol")
    assert infer_sport("Sıralama Turları", "formula-1-hangi-kanalda") == (99, "Formula 1")
    assert infer_sport("Nilüfer - Beşiktaş", "hentbol-erkekler") == (0, "Other")


def test_team_page_keeps_mens_football_and_fener_basket() -> None:
    raw = broadcasts_from_html(TEAM_HTML, "https://www.sporekrani.com/home/team/fenerbahce")
    events = filter_broadcasts(raw)
    titles = [item["title"] for item in events]
    assert "Fenerbahçe - Eyüpspor" in titles
    assert "Ç.Rizespor - Fenerbahçe" in titles
    assert "Fenerbahçe Tarfin - Bayern Münih" in titles
    assert "Beşiktaş - Fenerbahçe" not in titles
    assert "Real Madrid - Olympiakos" not in titles
    eyup = next(item for item in events if item["title"] == "Fenerbahçe - Eyüpspor")
    assert eyup["starts_at_istanbul"] == "2026-09-20 17:00:00"
    assert eyup["starts_at_utc"] == "2026-09-20 14:00:00"
    assert eyup["channels"] == ["Bein Sports 1"]
    assert eyup["source"] == "sporekrani"


def test_women_url_is_dropped_even_without_k_suffix() -> None:
    entities = classify_entities(
        "Beşiktaş - Fenerbahçe",
        1,
        "Futbol",
        "besiktas-fenerbahce-suwen-kadinlar-futbol-ligi",
    )
    assert entities == []


def test_f1_league_urls_skip_practice() -> None:
    urls = f1_match_urls(F1_LEAGUE_HTML)
    joined = " ".join(urls)
    assert "siralama-turlari" in joined
    assert "azerbaycan-gp" in joined
    assert "antrenman" not in joined


def test_f1_match_page_uses_sports_event_title_and_channel() -> None:
    raw = broadcasts_from_html(
        F1_MATCH_HTML,
        "https://www.sporekrani.com/home/match/481463/2026/09/25/siralama-turlari-azerbaycan-gp-formula-1-hangi-kanalda",
    )
    events = filter_broadcasts(raw)
    assert len(events) == 1
    assert events[0]["title"] == "Formula 1 - Sıralama Turları"
    assert events[0]["channels"] == ["Bein Sports 4"]
    assert events[0]["starts_at_istanbul"] == "2026-09-25 15:00:00"
    assert events[0]["entity_ids"] == ["formula1"]


def test_f1_gp_title_is_kept() -> None:
    assert classify_entities("Formula 1 - Azerbaycan GP", 99, "Formula 1") == ["formula1"]


def test_merge_prefers_sahadan_on_overlap() -> None:
    sahadan = filter_broadcasts(SAHADAN)
    extra = filter_broadcasts(
        broadcasts_from_html(TEAM_HTML, "https://www.sporekrani.com/home/team/fenerbahce")
    )
    merged = merge_events(sahadan, extra)
    eyup = [item for item in merged if item["title"] == "Fenerbahçe - Eyüpspor"]
    assert len(eyup) == 1
    assert eyup[0]["source"] == "sahadan"
    later = [item for item in merged if item["title"] == "Ç.Rizespor - Fenerbahçe"]
    assert later and later[0]["source"] == "sporekrani"


def test_dense_day_has_seven_events() -> None:
    demo = dense_day_demo_events()
    assert len(demo) == 7
    days = {item["starts_at_istanbul"][:10] for item in demo}
    assert days == {"2026-09-23"}
    document = build_document([], include_demo=True, sporekrani_raw=[])
    titles = [item["title"] for item in document["events"]]
    assert sum(title.startswith("[DEMO]") for title in titles) == 7
    live = build_document([], include_demo=False, sporekrani_raw=[])
    assert live["events"] == []
