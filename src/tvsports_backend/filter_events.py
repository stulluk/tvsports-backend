"""Select only the broadcasts the TVsports app should show."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

ISTANBUL = ZoneInfo("Europe/Istanbul")
SAHADAN_NAIVE = "%Y-%m-%d %H:%M:%S"

SPORT_FOOTBALL = 1
SPORT_BASKETBALL = 2

ENTITY_FENER_FOOTBALL = "fenerbahce_football"
ENTITY_FENER_BASKETBALL = "fenerbahce_basketball"
ENTITY_GS = "galatasaray"
ENTITY_BJK = "besiktas"
ENTITY_TS = "trabzonspor"
ENTITY_REAL = "real_madrid"
ENTITY_BARCA = "barcelona"
ENTITY_F1 = "formula1"

WOMEN_MARK = re.compile(
    r"\(k\)|kadinlar|kadınlar|\bwomen\b",
    re.IGNORECASE,
)
YOUTH_MARK = re.compile(r"\b(u1[5-9]|u2[0-3]|genç|genc|koleji)\b", re.IGNORECASE)
F1_KEEP = re.compile(
    r"sıralama|siralama|qualif|quali|sprint|yarış|yaris|\brace\b|\bgp\b",
    re.IGNORECASE,
)
F1_DROP = re.compile(
    r"antrenman|practice|\bfp[1-3]\b|serbest|free practice",
    re.IGNORECASE,
)
F4_MARK = re.compile(r"formula\s*4|\bf4\b", re.IGNORECASE)
F1_MARK = re.compile(r"formula\s*1|\bf1\b", re.IGNORECASE)


def _norm(text: str) -> str:
    """Return a lowercase ASCII-ish form for team matching."""
    table = str.maketrans(
        {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
            "Ç": "c",
            "Ğ": "g",
            "İ": "i",
            "Ö": "o",
            "Ş": "s",
            "Ü": "u",
        }
    )
    return text.translate(table).lower()


# Dropped after normalize so "Amed SK" and "Amedspor" share the token "amed".
GENERIC_CLUB_TOKENS = {
    "sk",
    "fk",
    "afc",
    "fc",
    "cf",
    "bld",
    "belediyesi",
    "belediye",
    "basket",
    "basketbol",
    "kulubu",
    "club",
    "jk",
    "as",
    "ac",
}
# Extra tokens that mean a different squad, not a spelling variant.
BRANCH_CLUB_TOKENS = {"tarfin", "koleji", "mct", "k"}
CLUB_PUNCT = re.compile(r"[^a-z0-9\s.]")


def club_tokens(name: str) -> tuple[str, ...]:
    """Return comparable tokens for a club name.

    Strips punctuation, generic suffixes (SK / FK / Basket), and a trailing
    ``spor`` so ``Amedspor`` and ``Amed SK`` both become ``("amed",)``.
    Branch markers such as Tarfin / Koleji are kept.
    """
    cleaned = CLUB_PUNCT.sub(" ", _norm(name)).replace(".", " ")
    tokens: list[str] = []
    for raw in cleaned.split():
        if raw in GENERIC_CLUB_TOKENS:
            continue
        if raw.endswith("spor") and len(raw) > 4:
            raw = raw[:-4]
        if raw:
            tokens.append(raw)
    return tuple(tokens)


def tokens_similar(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    """Return True when two token tuples name the same club."""
    if left == right:
        return True
    if not left or not right:
        return False
    if len(left) == len(right) and all(
        a == b or a.startswith(b) or b.startswith(a) for a, b in zip(left, right)
    ):
        return True
    extra: set[str]
    if set(left) <= set(right):
        extra = set(right) - set(left)
    elif set(right) <= set(left):
        extra = set(left) - set(right)
    else:
        return False
    return not extra.intersection(BRANCH_CLUB_TOKENS)


def sides_match(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Return True when home/away name the same pairing, order ignored."""
    a_home = club_tokens(str(first.get("home") or ""))
    a_away = club_tokens(str(first.get("away") or ""))
    b_home = club_tokens(str(second.get("home") or ""))
    b_away = club_tokens(str(second.get("away") or ""))
    return (
        tokens_similar(a_home, b_home) and tokens_similar(a_away, b_away)
    ) or (
        tokens_similar(a_home, b_away) and tokens_similar(a_away, b_home)
    )


def kickoff_minutes(event: dict[str, Any]) -> int | None:
    """Return Istanbul kickoff as minutes from midnight, or None."""
    stamp = str(event.get("starts_at_istanbul") or "")
    if len(stamp) < 16:
        return None
    try:
        hour, minute = stamp[11:16].split(":")
        return int(hour) * 60 + int(minute)
    except ValueError:
        return None


def is_same_fixture(
    first: dict[str, Any],
    second: dict[str, Any],
    window_minutes: int = 30,
) -> bool:
    """Return True when two rows are the same match under different spellings."""
    day_a = str(first.get("starts_at_istanbul") or "")[:10]
    day_b = str(second.get("starts_at_istanbul") or "")[:10]
    if not day_a or day_a != day_b:
        return False
    time_a = kickoff_minutes(first)
    time_b = kickoff_minutes(second)
    if time_a is None or time_b is None:
        return False
    if abs(time_a - time_b) > window_minutes:
        return False
    sport_a = first.get("sport_id")
    sport_b = second.get("sport_id")
    if sport_a and sport_b and sport_a != sport_b:
        return False
    return sides_match(first, second)


def _sides(match_name: str) -> tuple[str, str]:
    """Split 'Home - Away' and return both sides (empty away if no dash)."""
    parts = [part.strip() for part in match_name.split(" - ", 1)]
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _is_mens_senior_football(match_name: str, extra_text: str = "") -> bool:
    """Return True when the listing is men's first-team football."""
    blob = f"{match_name} {extra_text}"
    if WOMEN_MARK.search(blob):
        return False
    if YOUTH_MARK.search(blob):
        return False
    return True


def _mentions(side: str, *needles: str) -> bool:
    """Return True if any needle appears as a team token on one side."""
    nside = _norm(side)
    return any(needle in nside for needle in needles)


def is_formula1_broadcast(match_name: str, sport_name: str) -> bool:
    """Return True for Formula 1 quali / sprint / race listings only."""
    blob = f"{match_name} {sport_name}"
    if F4_MARK.search(blob):
        return False
    if not F1_MARK.search(blob):
        return False
    if F1_DROP.search(match_name):
        return False
    return bool(F1_KEEP.search(match_name) or F1_KEEP.search(sport_name))


def classify_entities(
    match_name: str,
    sport: int,
    sport_name: str,
    extra_text: str = "",
) -> list[str]:
    """Return entity ids that this broadcast belongs to."""
    home, away = _sides(match_name)
    entities: list[str] = []

    if is_formula1_broadcast(match_name, sport_name):
        entities.append(ENTITY_F1)
        return entities

    if sport == SPORT_FOOTBALL and _is_mens_senior_football(match_name, extra_text):
        for side in (home, away, match_name):
            if _mentions(side, "fenerbahce") and not _mentions(side, "tarfin"):
                entities.append(ENTITY_FENER_FOOTBALL)
                break
        for side in (home, away):
            if _mentions(side, "galatasaray") and not _mentions(side, "mct"):
                entities.append(ENTITY_GS)
            if _mentions(side, "besiktas"):
                entities.append(ENTITY_BJK)
            if _mentions(side, "trabzonspor"):
                entities.append(ENTITY_TS)
            if _mentions(side, "real madrid"):
                entities.append(ENTITY_REAL)
            if _mentions(side, "barcelona"):
                entities.append(ENTITY_BARCA)

    if sport == SPORT_BASKETBALL:
        if _mentions(match_name, "fenerbahce"):
            entities.append(ENTITY_FENER_BASKETBALL)

    # Preserve order, drop duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for item in entities:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def sahadan_utc_to_istanbul(raw: str | None) -> tuple[str | None, str | None]:
    """Parse Sahadan's naive UTC stamp and return (utc, istanbul) wall strings.

    Sahadan stores ``date_time_utc`` as ``YYYY-MM-DD HH:MM:SS`` without a
    zone, then the website does ``new Date(value.replace(' ','T')+'Z')`` and
    shows it in the browser timezone. For Turkey that is Europe/Istanbul
    (UTC+3, no DST). We do the same conversion so the app matches the site.
    """
    if not raw:
        return None, None
    try:
        utc = datetime.strptime(raw, SAHADAN_NAIVE).replace(tzinfo=timezone.utc)
    except ValueError:
        return raw, raw
    istanbul = utc.astimezone(ISTANBUL)
    return utc.strftime(SAHADAN_NAIVE), istanbul.strftime(SAHADAN_NAIVE)


def channel_names(raw: dict[str, Any]) -> list[str]:
    """Collect TV and digital channel names from a Sahadan broadcast."""
    names: list[str] = []
    for key in ("channels", "digital_channels"):
        for item in raw.get(key) or []:
            name = (item or {}).get("name")
            if name and name not in names:
                names.append(name)
    return names


def filter_broadcasts(raw_broadcasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep broadcasts that match at least one followed entity."""
    kept: list[dict[str, Any]] = []
    for item in raw_broadcasts:
        match = item.get("match") or {}
        name = match.get("name") or ""
        sport = int(match.get("sport") or 0)
        sport_name = match.get("sport_name") or ""
        extra = str(item.get("source_url") or item.get("extra_text") or "")
        entities = classify_entities(name, sport, sport_name, extra)
        if not entities:
            continue
        home, away = _sides(name)
        utc_stamp, istanbul_stamp = sahadan_utc_to_istanbul(item.get("date_time_utc"))
        kept.append(
            {
                "id": str(match.get("uuid") or match.get("mid") or name),
                "source_match_id": match.get("id"),
                "starts_at_utc": utc_stamp,
                "starts_at_istanbul": istanbul_stamp,
                "title": name,
                "home": home,
                "away": away,
                "sport": sport_name,
                "sport_id": sport,
                "channels": channel_names(item),
                "entity_ids": entities,
                "source": item.get("source") or "sahadan",
            }
        )
    kept.sort(key=lambda row: (row.get("starts_at_utc") or "", row.get("title") or ""))
    return kept
