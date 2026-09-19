"""Club-name collision tests for Sahadan + Spor Ekranı merge."""

from __future__ import annotations

from tvsports_backend.filter_events import club_tokens, is_same_fixture
from tvsports_backend.publish import merge_events


def _row(
    title: str,
    home: str,
    away: str,
    istanbul: str,
    source: str,
    sport_id: int = 1,
) -> dict:
    return {
        "id": f"{source}-{title}",
        "title": title,
        "home": home,
        "away": away,
        "starts_at_istanbul": istanbul,
        "starts_at_utc": istanbul,
        "sport_id": sport_id,
        "sport": "Futbol" if sport_id == 1 else "Basketbol",
        "channels": [source],
        "entity_ids": ["besiktas"] if "Beşiktaş" in title else [],
        "source": source,
    }


def test_club_tokens_collapse_amed_and_dubai() -> None:
    assert club_tokens("Amed SK") == ("amed",)
    assert club_tokens("Amedspor") == ("amed",)
    assert club_tokens("Dubai Basket") == ("dubai",)
    assert club_tokens("Dubai") == ("dubai",)
    assert club_tokens("Atl. Madrid") == ("atl", "madrid")
    assert club_tokens("Atletico Madrid") == ("atletico", "madrid")
    assert club_tokens("Fenerbahçe Tarfin") == ("fenerbahce", "tarfin")
    assert club_tokens("Fenerbahçe") == ("fenerbahce",)


def test_amed_atl_dubai_pairs_are_same_fixture() -> None:
    assert is_same_fixture(
        _row("Amed SK - Beşiktaş", "Amed SK", "Beşiktaş", "2026-09-20 20:00:00", "sahadan"),
        _row("Amedspor - Beşiktaş", "Amedspor", "Beşiktaş", "2026-09-20 20:00:00", "sporekrani"),
    )
    assert is_same_fixture(
        _row("Atl. Madrid - Real Madrid", "Atl. Madrid", "Real Madrid", "2026-09-20 17:15:00", "sahadan"),
        _row("Atletico Madrid - Real Madrid", "Atletico Madrid", "Real Madrid", "2026-09-20 17:15:00", "sporekrani"),
    )
    assert is_same_fixture(
        _row("Fenerbahçe Tarfin - Dubai", "Fenerbahçe Tarfin", "Dubai", "2026-09-19 17:00:00", "sahadan", 2),
        _row("Dubai Basket - Fenerbahçe Tarfin", "Dubai Basket", "Fenerbahçe Tarfin", "2026-09-19 17:00:00", "sporekrani", 2),
    )


def test_does_not_merge_fener_football_with_tarfin() -> None:
    assert not is_same_fixture(
        _row("Fenerbahçe - Eyüpspor", "Fenerbahçe", "Eyüpspor", "2026-09-20 17:00:00", "sahadan", 1),
        _row("Fenerbahçe Tarfin - Demo", "Fenerbahçe Tarfin", "Demo", "2026-09-20 17:00:00", "sporekrani", 2),
    )


def test_does_not_merge_two_f1_sessions_same_day() -> None:
    assert not is_same_fixture(
        {
            "title": "Formula 1 - Sprint Yarışı",
            "home": "Formula 1",
            "away": "Sprint Yarışı",
            "starts_at_istanbul": "2026-10-10 12:00:00",
            "sport_id": 99,
        },
        {
            "title": "Formula 1 - Sıralama Turları",
            "home": "Formula 1",
            "away": "Sıralama Turları",
            "starts_at_istanbul": "2026-10-10 16:00:00",
            "sport_id": 99,
        },
    )


def test_merge_drops_sporekrani_spelling_variant() -> None:
    sahadan = [
        _row("Amed SK - Beşiktaş", "Amed SK", "Beşiktaş", "2026-09-20 20:00:00", "sahadan"),
    ]
    extra = [
        _row("Amedspor - Beşiktaş", "Amedspor", "Beşiktaş", "2026-09-20 20:00:00", "sporekrani"),
        _row("Ç.Rizespor - Fenerbahçe", "Ç.Rizespor", "Fenerbahçe", "2026-10-10 19:00:00", "sporekrani"),
    ]
    merged = merge_events(sahadan, extra)
    titles = [item["title"] for item in merged]
    assert titles == ["Amed SK - Beşiktaş", "Ç.Rizespor - Fenerbahçe"]
    assert merged[0]["source"] == "sahadan"
