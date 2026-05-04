from __future__ import annotations

import re
from typing import Iterable

ODDS_ONLY_RE = re.compile(r"^(?:\d{1,3}\.\d{2,4})(?:\s+\d{1,3}\.\d{2,4})*$")
TIME_RE = re.compile(r"(?<!\d)(?:[01]?\d|2[0-3]):[0-5]\d")

LOW_VALUE_NAVIGATION = {
    "account",
    "all",
    "back",
    "balance",
    "betslip",
    "cashout",
    "close",
    "deposit",
    "forgot password",
    "help",
    "home",
    "join",
    "login",
    "logout",
    "menu",
    "my bets",
    "next",
    "open",
    "password",
    "promotions",
    "register",
    "search",
    "settings",
    "sign in",
    "sign up",
    "sportsbook",
    "submit",
    "username",
}


def clean_lines(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        raw_lines = re.split(r"[\r\n]+", value)
    else:
        raw_lines = []
        for item in value:
            raw_lines.extend(re.split(r"[\r\n]+", str(item)))

    cleaned: list[str] = []
    seen_non_odds: set[str] = set()
    last_line = ""

    for raw in raw_lines:
        line = normalize_line(raw)
        if not line:
            continue
        if is_low_value_navigation(line):
            continue
        if line == last_line:
            continue
        if line in seen_non_odds and not _is_value_line(line):
            continue
        if not _is_value_line(line):
            seen_non_odds.add(line)
        cleaned.append(line)
        last_line = line

    return cleaned


def normalize_line(value: str) -> str:
    line = value.replace("\u00a0", " ")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_low_value_navigation(line: str) -> bool:
    normalized = normalize_line(line).lower()
    if normalized in LOW_VALUE_NAVIGATION:
        return True
    if len(normalized) <= 2 and normalized not in {"1", "x", "2"}:
        return True
    return False


def _is_value_line(line: str) -> bool:
    return bool(ODDS_ONLY_RE.match(line) or TIME_RE.search(line))
