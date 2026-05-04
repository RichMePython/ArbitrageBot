from __future__ import annotations

import re
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from .content_cleaning_service import clean_lines

ODDS_RE = re.compile(r"(?<![\d.])(?:[1-9]\d{0,2})(?:\.\d{2,4})(?![\d.])")
TIME_RE = re.compile(r"(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d")
DATE_RE = re.compile(
    r"\b(?:(?:20\d{2})[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])|"
    r"(?:0?[1-9]|[12]\d|3[01])[-/](?:0?[1-9]|1[0-2])[-/](?:20\d{2}))\b"
)

KNOWN_SPORTS = {
    "football",
    "soccer",
    "basketball",
    "beach volley",
    "tennis",
    "cricket",
    "esoccer",
    "rugby",
    "rugby league",
    "rugby union",
    "baseball",
    "ice hockey",
    "hockey",
    "volleyball",
    "waterpolo",
    "handball",
    "futsal",
    "boxing",
    "mma",
    "ufc",
    "golf",
    "darts",
    "snooker",
    "table tennis",
    "esports",
    "american football",
    "aussie rules",
    "motorsport",
    "cycling",
    "netball",
}

MARKET_HINTS = {
    "1x2",
    "match winner",
    "winner",
    "moneyline",
    "draw no bet",
    "double chance",
    "both teams to score",
    "total goals",
    "over/under",
    "over under",
    "handicap",
    "spread",
    "correct score",
    "first half",
    "halftime",
    "fulltime",
    "to qualify",
    "set winner",
    "game winner",
    "innings",
}

COMPETITION_HINTS = {
    "league",
    "cup",
    "championship",
    "premier",
    "division",
    "serie",
    "la liga",
    "liga",
    "eredivisie",
    "bundesliga",
    "ligue",
    "uefa",
    "fifa",
    "copa",
    "nba",
    "nfl",
    "mlb",
    "nhl",
    "international",
    "world",
    "national",
    "tournament",
    "women",
    "reserves",
}

SECTION_HINTS = {
    "upcoming",
    "live",
    "today",
    "tomorrow",
    "popular",
    "highlights",
    "featured",
    "top leagues",
    "sports",
    "competitions",
}


def parse_visible_content(lines: list[str] | str, source_url: str, page_title: Optional[str] = None) -> dict:
    readable_lines = clean_lines(lines)
    active_sport_index, navigation_sport_indexes = detect_sport_navigation(readable_lines)
    sports: list[dict] = []
    page_sections: list[str] = []
    labels: list[str] = []
    warnings: list[str] = []

    current_sport: Optional[dict] = None
    current_competition: Optional[dict] = None
    current_event: Optional[dict] = None
    current_market: Optional[dict] = None
    pending_date: Optional[str] = None
    pending_time: Optional[str] = None
    recent_labels: deque[str] = deque(maxlen=6)

    for line_index, line in enumerate(readable_lines):
        lower = line.lower()
        date_value, time_value = extract_date_time(line)
        if date_value:
            pending_date = date_value
        if time_value:
            pending_time = time_value

        if is_section(line):
            _append_unique(page_sections, line)

        sport_name = sport_from_line(line)
        if sport_name:
            sport = ensure_sport(sports, sport_name)
            if line_index == active_sport_index or line_index not in navigation_sport_indexes:
                current_sport = sport
                current_competition = None
                current_event = None
                current_market = None
            recent_labels.append(line)
            continue

        if is_market(line):
            if current_event is None:
                recent_labels.append(line)
                continue
            current_market = ensure_market(current_event, normalize_market_name(line))
            recent_labels.append(line)
            continue

        if is_competition(line) and current_sport:
            current_competition = ensure_competition(current_sport, line)
            current_event = None
            current_market = None
            recent_labels.append(line)
            continue

        if is_event(line):
            current_event = ensure_event(
                current_sport,
                current_competition,
                sports,
                clean_event_name(line),
                pending_date or date_value,
                pending_time or time_value,
            )
            current_market = ensure_market(current_event, infer_default_market(current_event))
            recent_labels.append(line)
            continue

        if current_event and (date_value or time_value):
            if date_value and not current_event.get("start_date"):
                current_event["start_date"] = date_value
            if time_value and not current_event.get("start_time"):
                current_event["start_time"] = time_value

        odds_values = extract_odds(line)
        if odds_values:
            inferred_event_name = infer_event_from_recent_labels(recent_labels)
            if inferred_event_name:
                current_event = ensure_event(
                    current_sport,
                    current_competition,
                    sports,
                    inferred_event_name,
                    pending_date,
                    pending_time,
                )
                current_market = None
            if current_event is None:
                current_event = ensure_event(
                    current_sport,
                    current_competition,
                    sports,
                    "Unlinked visible odds",
                    pending_date,
                    pending_time,
                )
            market_name = infer_market_for_odds(odds_values, current_event, recent_labels, current_market)
            if market_name:
                current_market = ensure_market(current_event, market_name)
            elif current_market is None:
                current_market = ensure_market(current_event, infer_default_market(current_event))

            selection_names = infer_selection_names(line, odds_values, current_event, recent_labels)
            for index, odds in enumerate(odds_values):
                selection_name = selection_names[index] if index < len(selection_names) else f"Selection {index + 1}"
                append_selection(current_market, selection_name, odds, 78 if selection_name.startswith("Selection") else 86)
            recent_labels.append(line)
            continue

        if is_total_line(line):
            _append_unique(labels, line)
            recent_labels.append(line)
            continue

        if should_preserve_label(line):
            _append_unique(labels, line)
            recent_labels.append(line)

    if not sports and readable_lines:
        warnings.append("Readable text was found, but no sport hierarchy could be identified.")
    if sports and not flatten_events({"sports": sports}):
        warnings.append("Sports were found, but visible events could not be linked cleanly.")
    if sports and not flatten_odds({"sports": sports}):
        warnings.append("No decimal odds were found in the extracted visible text.")

    return {
        "sports": sports,
        "page_sections": page_sections,
        "labels": labels,
        "warnings": warnings,
    }


def score_extraction(method: str, raw_lines: list[str], structured_content: dict, warnings: list[str]) -> int:
    event_count = len(flatten_events(structured_content))
    odds_count = len(flatten_odds(structured_content))
    sport_count = len(structured_content.get("sports", []))
    line_count = len(raw_lines)

    score = 25
    if line_count >= 10:
        score += 15
    if line_count >= 30:
        score += 10
    score += min(sport_count * 8, 16)
    score += min(event_count * 5, 25)
    score += min(odds_count * 2, 22)

    if method == "browser_automation":
        score += 6
    elif method == "ai_vision_reader":
        score += 4
    elif method == "html_extraction":
        score += 2

    score -= min(len(warnings) * 5, 20)
    return max(0, min(score, 98))


def flatten_events(structured_content: dict) -> list[dict]:
    events: list[dict] = []
    for sport in structured_content.get("sports", []):
        for competition in sport.get("competitions", []):
            for event in competition.get("events", []):
                events.append(
                    {
                        "sport_name": sport.get("sport_name"),
                        "competition_name": competition.get("competition_name"),
                        "event_name": event.get("event_name"),
                        "start_date": event.get("start_date"),
                        "start_time": event.get("start_time"),
                    }
                )
    return events


def flatten_odds(structured_content: dict) -> list[dict]:
    odds_rows: list[dict] = []
    for sport in structured_content.get("sports", []):
        for competition in sport.get("competitions", []):
            for event in competition.get("events", []):
                for market in event.get("markets", []):
                    for selection in market.get("selections", []):
                        odds_rows.append(
                            {
                                "sport_name": sport.get("sport_name"),
                                "competition_name": competition.get("competition_name"),
                                "event_name": event.get("event_name"),
                                "market_name": market.get("market_name"),
                                "selection_name": selection.get("selection_name"),
                                "odds": selection.get("odds"),
                            }
                        )
    return odds_rows


def extract_odds(line: str) -> list[str]:
    compact_values = extract_compact_odds(line)
    if compact_values:
        return compact_values

    values: list[str] = []
    for match in ODDS_RE.finditer(line):
        value = match.group(0)
        try:
            decimal = float(value)
        except ValueError:
            continue
        if 1.01 <= decimal <= 1000:
            values.append(value)
    return values


def extract_compact_odds(line: str) -> list[str]:
    compact = re.sub(r"\s+", "", line)
    if not re.fullmatch(r"\d[\d.]*", compact or ""):
        return []
    if compact.count(".") < 2:
        return []

    values: list[str] = []
    index = 0
    while index < len(compact):
        match = re.match(r"\d{1,3}\.\d{2}", compact[index:])
        if not match:
            return []
        value = match.group(0)
        try:
            decimal = float(value)
        except ValueError:
            return []
        if not 1.01 <= decimal <= 1000:
            return []
        values.append(value)
        index += len(value)

    return values if len(values) > 1 else []


def extract_date_time(line: str) -> tuple[Optional[str], Optional[str]]:
    date_value: Optional[str] = None
    time_value: Optional[str] = None

    date_match = DATE_RE.search(line)
    if date_match:
        date_value = normalize_date(date_match.group(0))
    else:
        lower = line.lower()
        today = datetime.now(timezone.utc).date()
        if "today" in lower:
            date_value = today.isoformat()
        elif "tomorrow" in lower:
            date_value = (today + timedelta(days=1)).isoformat()

    time_match = TIME_RE.search(line)
    if time_match:
        time_value = time_match.group(0)

    return date_value, time_value


def normalize_date(value: str) -> str:
    normalized = value.replace("/", "-")
    parts = normalized.split("-")
    if len(parts) != 3:
        return normalized
    if len(parts[0]) == 4:
        year, month, day = parts
    else:
        day, month, year = parts
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def sport_from_line(line: str) -> Optional[str]:
    normalized = line.strip().lower()
    if normalized in KNOWN_SPORTS:
        return title_case(line)
    return None


def detect_sport_navigation(lines: list[str]) -> tuple[Optional[int], set[int]]:
    sport_indexes = [index for index, line in enumerate(lines) if sport_from_line(line)]
    navigation_indexes: set[int] = set()
    active_index: Optional[int] = None

    for index in sport_indexes:
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if re.fullmatch(r"\(\d+\)", next_line):
            navigation_indexes.add(index)

    upcoming_index = next((index for index, line in enumerate(lines) if line.lower() == "upcoming"), None)
    if upcoming_index is not None:
        end_index = next(
            (
                index
                for index in range(upcoming_index + 1, len(lines))
                if lines[index].lower() in {"by time", "today", "highlights"}
            ),
            min(len(lines), upcoming_index + 20),
        )
        tab_sport_indexes = [
            index
            for index in range(upcoming_index + 1, end_index)
            if sport_from_line(lines[index])
        ]
        navigation_indexes.update(tab_sport_indexes)
        if tab_sport_indexes:
            active_index = tab_sport_indexes[0]

    return active_index, navigation_indexes


def is_section(line: str) -> bool:
    lower = line.lower()
    if lower in SECTION_HINTS:
        return True
    return any(len(hint) > 5 and hint in lower for hint in SECTION_HINTS)


def is_market(line: str) -> bool:
    lower = line.lower()
    if lower in {"1", "x", "2", "1 x 2", "1x2"}:
        return True
    return any(hint in lower for hint in MARKET_HINTS)


def is_event(line: str) -> bool:
    if extract_odds(line):
        return False
    if is_competition(line):
        return False
    lower = f" {line.lower()} "
    if any(token in lower for token in [" vs ", " v ", " versus ", " @ "]):
        return _has_two_named_sides(line)
    if " - " in line or " / " in line:
        return _has_two_named_sides(line)
    return False


def is_competition(line: str) -> bool:
    if extract_odds(line) or is_market(line):
        return False
    lower = line.lower()
    return any(hint in lower for hint in COMPETITION_HINTS)


def should_preserve_label(line: str) -> bool:
    if extract_odds(line):
        return False
    if len(line) > 120:
        return False
    return bool(re.search(r"[A-Za-z]", line))


def ensure_sport(sports: list[dict], sport_name: str) -> dict:
    for sport in sports:
        if sport.get("sport_name", "").lower() == sport_name.lower():
            return sport
    sport = {"sport_name": sport_name, "competitions": []}
    sports.append(sport)
    return sport


def ensure_competition(sport: dict, competition_name: Optional[str]) -> dict:
    name = competition_name or "Unspecified competition"
    for competition in sport["competitions"]:
        if competition.get("competition_name") == name:
            return competition
    competition = {"competition_name": name, "events": []}
    sport["competitions"].append(competition)
    return competition


def ensure_event(
    current_sport: Optional[dict],
    current_competition: Optional[dict],
    sports: list[dict],
    event_name: str,
    start_date: Optional[str],
    start_time: Optional[str],
) -> dict:
    sport = current_sport or ensure_sport(sports, "Unknown sport")
    competition = current_competition or ensure_competition(sport, "Unspecified competition")
    for event in competition["events"]:
        if event.get("event_name") == event_name:
            if start_date and not event.get("start_date"):
                event["start_date"] = start_date
            if start_time and not event.get("start_time"):
                event["start_time"] = start_time
            return event
    event = {
        "id": str(uuid.uuid4()),
        "event_name": event_name,
        "start_date": start_date,
        "start_time": start_time,
        "markets": [],
    }
    competition["events"].append(event)
    return event


def ensure_market(event: dict, market_name: str) -> dict:
    for market in event["markets"]:
        if market.get("market_name") == market_name:
            return market
    market = {
        "id": str(uuid.uuid4()),
        "market_name": market_name,
        "selections": [],
        "confidence_score": 82,
    }
    event["markets"].append(market)
    return market


def append_selection(market: dict, selection_name: str, odds: str, confidence: int) -> None:
    selection_name = selection_name.strip(" :-") or "Unlinked selection"
    key = (selection_name.lower(), odds)
    for existing in market["selections"]:
        if (existing.get("selection_name", "").lower(), existing.get("odds")) == key:
            return
    market["selections"].append(
        {
            "selection_name": selection_name,
            "odds": odds,
            "confidence_score": confidence,
        }
    )


def infer_selection_names(line: str, odds_values: list[str], current_event: dict, recent_labels: deque[str]) -> list[str]:
    total_line = recent_total_line(recent_labels)
    if total_line and len(odds_values) == 2:
        return [f"Over {total_line}", f"Under {total_line}"]

    names = extract_selection_names_from_line(line, odds_values)
    if len(names) >= len(odds_values):
        return names

    event_name = current_event.get("event_name") or ""
    participants = split_event_participants(event_name)
    if len(odds_values) == 3 and len(participants) >= 2:
        return [participants[0], "Draw", participants[1]]
    if len(odds_values) == 2 and len(participants) >= 2:
        return [participants[0], participants[1]]

    meaningful_recent = [
        label
        for label in reversed(recent_labels)
        if not extract_odds(label) and not is_market(label) and not is_event(label)
    ]
    if len(odds_values) == 1 and meaningful_recent:
        return [meaningful_recent[0]]

    return [f"Selection {index + 1}" for index in range(len(odds_values))]


def infer_event_from_recent_labels(recent_labels: deque[str]) -> Optional[str]:
    candidates: list[str] = []
    for label in reversed(recent_labels):
        if not is_team_candidate(label):
            continue
        candidates.append(label)
        if len(candidates) == 2:
            break
    if len(candidates) != 2:
        return None
    away, home = candidates
    return f"{home} vs {away}"


def is_team_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False
    if extract_odds(stripped) or is_market(stripped) or is_competition(stripped) or sport_from_line(stripped):
        return False
    if is_section(stripped):
        return False
    if DATE_RE.search(stripped) or TIME_RE.search(stripped):
        return False
    if re.fullmatch(r"\+?\d+(?:#\d+)?", stripped):
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?", stripped):
        return False
    return bool(re.search(r"[A-Za-z]", stripped))


def infer_market_for_odds(
    odds_values: list[str],
    current_event: dict,
    recent_labels: deque[str],
    current_market: Optional[dict],
) -> Optional[str]:
    total_line = recent_total_line(recent_labels)
    if len(odds_values) == 2 and total_line:
        return f"Under/Over {total_line}"
    if len(odds_values) == 3 and split_event_participants(current_event.get("event_name", "")):
        return "1X2"
    if current_market:
        return current_market.get("market_name")
    return None


def recent_total_line(recent_labels: deque[str]) -> Optional[str]:
    for label in reversed(recent_labels):
        if is_total_line(label):
            return label.strip()
        if extract_odds(label) or is_event(label):
            break
    return None


def is_total_line(line: str) -> bool:
    stripped = line.strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", stripped):
        return False
    try:
        value = float(stripped)
    except ValueError:
        return False
    return 0.5 <= value <= 20


def extract_selection_names_from_line(line: str, odds_values: list[str]) -> list[str]:
    matches = list(ODDS_RE.finditer(line))
    names: list[str] = []
    previous_end = 0
    for match in matches:
        segment = line[previous_end : match.start()]
        segment = re.sub(r"\b(?:odds|price|@)\b", " ", segment, flags=re.IGNORECASE)
        segment = re.sub(r"[:|]+", " ", segment)
        segment = re.sub(r"\s+", " ", segment).strip(" -")
        if segment and not extract_odds(segment) and len(segment) <= 80:
            names.append(segment)
        previous_end = match.end()
    if len(names) == len(odds_values):
        return names
    return names


def split_event_participants(event_name: str) -> list[str]:
    if event_name.lower().startswith("unlinked"):
        return []
    parts = re.split(r"\s+(?:vs|v|versus|@)\s+|\s+-\s+|\s+/\s+", event_name, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def infer_default_market(event: dict) -> str:
    participants = split_event_participants(event.get("event_name", ""))
    if len(participants) == 2:
        return "Match Winner"
    return "Unspecified market"


def normalize_market_name(line: str) -> str:
    lower = line.strip().lower().replace(" ", "")
    if lower in {"1x2", "1x2market"}:
        return "1X2"
    if line.strip().lower() == "1 x 2":
        return "1X2"
    return title_case(line.strip())


def clean_event_name(line: str) -> str:
    value = DATE_RE.sub("", line)
    value = TIME_RE.sub("", value)
    value = re.sub(r"\s+", " ", value).strip(" -")
    return value


def title_case(value: str) -> str:
    upper_tokens = {"nba", "nfl", "mlb", "nhl", "ufc", "mma", "uefa", "fifa"}
    words = []
    for word in value.strip().split():
        if word.lower() in upper_tokens:
            words.append(word.upper())
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _has_two_named_sides(line: str) -> bool:
    parts = split_event_participants(line)
    named = [part for part in parts if re.search(r"[A-Za-z]", part)]
    return len(named) >= 2


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
