from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Optional

from .config import DATA_DIR, DB_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@contextmanager
def db_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reading_sessions (
                id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                page_title TEXT,
                scan_status TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                confidence_score NUMERIC(5, 2),
                started_at TEXT NOT NULL,
                completed_at TEXT,
                warnings_json TEXT,
                result_json TEXT
            );

            CREATE TABLE IF NOT EXISTS extracted_text (
                id TEXT PRIMARY KEY,
                reading_session_id TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                text TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS extracted_events (
                id TEXT PRIMARY KEY,
                reading_session_id TEXT NOT NULL,
                sport_name TEXT,
                competition_name TEXT,
                event_name TEXT,
                start_date TEXT,
                start_time TEXT,
                source_url TEXT
            );

            CREATE TABLE IF NOT EXISTS extracted_markets (
                id TEXT PRIMARY KEY,
                reading_session_id TEXT NOT NULL,
                event_id TEXT,
                market_name TEXT,
                confidence_score NUMERIC(5, 2)
            );

            CREATE TABLE IF NOT EXISTS extracted_odds (
                id TEXT PRIMARY KEY,
                reading_session_id TEXT NOT NULL,
                event_id TEXT,
                market_name TEXT,
                selection_name TEXT,
                odds_value TEXT,
                odds_decimal NUMERIC(10, 4),
                confidence_score NUMERIC(5, 2)
            );

            CREATE TABLE IF NOT EXISTS extraction_logs (
                id TEXT PRIMARY KEY,
                reading_session_id TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def create_session(source_url: str) -> str:
    session_id = str(uuid.uuid4())
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO reading_sessions (
                id, source_url, scan_status, extraction_method, confidence_score, started_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, source_url, "running", "pending", 0, utc_now()),
        )
    return session_id


def log_event(session_id: str, level: str, message: str) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO extraction_logs (id, reading_session_id, level, message, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), session_id, level, message, utc_now()),
        )


def complete_session(session_id: str, result: dict) -> None:
    warnings = result.get("warnings", [])
    structured = result.get("structured_content", {})
    raw_text = result.get("raw_text", [])

    with db_connection() as conn:
        conn.execute("DELETE FROM extracted_text WHERE reading_session_id = ?", (session_id,))
        conn.execute("DELETE FROM extracted_events WHERE reading_session_id = ?", (session_id,))
        conn.execute("DELETE FROM extracted_markets WHERE reading_session_id = ?", (session_id,))
        conn.execute("DELETE FROM extracted_odds WHERE reading_session_id = ?", (session_id,))

        for line_number, text in enumerate(raw_text, start=1):
            conn.execute(
                """
                INSERT INTO extracted_text (id, reading_session_id, line_number, text)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), session_id, line_number, str(text)),
            )

        event_id_by_key: dict[str, str] = {}
        for sport in structured.get("sports", []):
            sport_name = sport.get("sport_name") or "Unknown sport"
            for competition in sport.get("competitions", []):
                competition_name = competition.get("competition_name")
                for event in competition.get("events", []):
                    event_id = event.get("id") or str(uuid.uuid4())
                    event_key = event.get("id") or _event_key(sport_name, competition_name, event)
                    event_id_by_key[event_key] = event_id
                    conn.execute(
                        """
                        INSERT INTO extracted_events (
                            id, reading_session_id, sport_name, competition_name, event_name,
                            start_date, start_time, source_url
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            session_id,
                            sport_name,
                            competition_name,
                            event.get("event_name"),
                            event.get("start_date"),
                            event.get("start_time"),
                            result.get("source_url"),
                        ),
                    )
                    for market in event.get("markets", []):
                        market_id = market.get("id") or str(uuid.uuid4())
                        market_name = market.get("market_name") or "Unspecified market"
                        conn.execute(
                            """
                            INSERT INTO extracted_markets (
                                id, reading_session_id, event_id, market_name, confidence_score
                            )
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                market_id,
                                session_id,
                                event_id,
                                market_name,
                                market.get("confidence_score", result.get("confidence_score")),
                            ),
                        )
                        for selection in market.get("selections", []):
                            odds_value = selection.get("odds")
                            conn.execute(
                                """
                                INSERT INTO extracted_odds (
                                    id, reading_session_id, event_id, market_name, selection_name,
                                    odds_value, odds_decimal, confidence_score
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    str(uuid.uuid4()),
                                    session_id,
                                    event_id,
                                    market_name,
                                    selection.get("selection_name"),
                                    odds_value,
                                    _decimal_or_none(odds_value),
                                    selection.get("confidence_score", market.get("confidence_score", result.get("confidence_score"))),
                                ),
                            )

        conn.execute(
            """
            UPDATE reading_sessions
            SET page_title = ?,
                scan_status = ?,
                extraction_method = ?,
                confidence_score = ?,
                completed_at = ?,
                warnings_json = ?,
                result_json = ?
            WHERE id = ?
            """,
            (
                result.get("page_title"),
                result.get("scan_status", "success"),
                result.get("extraction_method", "unknown"),
                result.get("confidence_score", 0),
                utc_now(),
                json.dumps(warnings),
                json.dumps(result),
                session_id,
            ),
        )


def fail_session(session_id: str, source_url: str, warnings: Iterable[str]) -> dict:
    result = {
        "scan_status": "failed",
        "source_url": source_url,
        "page_title": None,
        "extraction_method": "none",
        "timestamp": utc_now(),
        "confidence_score": 0,
        "total_stake": 100,
        "raw_text": [],
        "structured_content": {"sports": [], "page_sections": [], "labels": []},
        "section_1_all_available_sporting_events_and_odds": {
            "description": "This section contains all available sporting events and their odds extracted from the website.",
            "sports": [],
        },
        "section_2_arbitrage_analysis": {
            "description": "This section analyzes arbitrage possibility for each complete market.",
            "event_analyses": [],
            "analyzed_markets": [],
            "arbitrage_opportunities": [],
            "skipped_markets": [],
        },
        "section_3_arbitrage_summary": {
            "sports_found": 0,
            "competitions_found": 0,
            "events_found": 0,
            "markets_found": 0,
            "odds_extracted": 0,
            "complete_markets_analyzed": 0,
            "incomplete_markets_skipped": 0,
            "arbitrage_opportunities_found": 0,
            "best_arbitrage_opportunity": None,
            "best_arbitrage_profit_percentage": 0,
            "highest_profit_percentage": 0,
        },
        "warnings": list(warnings),
        "summary": {
            "sports_found": [],
            "events_found": [],
            "odds_found": [],
            "summary_text": f"Website scanned: {source_url}\nNo readable content could be extracted.",
        },
    }
    complete_session(session_id, result)
    return result


def get_session_result(session_id: str) -> Optional[dict]:
    with db_connection() as conn:
        if session_id == "latest":
            row = conn.execute(
                """
                SELECT result_json
                FROM reading_sessions
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT result_json FROM reading_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

    if not row or not row["result_json"]:
        return None
    return _ensure_arbitrage_sections(json.loads(row["result_json"]))


def list_sessions(limit: int = 25) -> list[dict]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, source_url, page_title, scan_status, extraction_method,
                   confidence_score, started_at, completed_at, warnings_json
            FROM reading_sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row["id"],
            "source_url": row["source_url"],
            "page_title": row["page_title"],
            "scan_status": row["scan_status"],
            "extraction_method": row["extraction_method"],
            "confidence_score": row["confidence_score"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "warnings": json.loads(row["warnings_json"] or "[]"),
        }
        for row in rows
    ]


def get_logs(session_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    with db_connection() as conn:
        if session_id:
            rows = conn.execute(
                """
                SELECT id, reading_session_id, level, message, created_at
                FROM extraction_logs
                WHERE reading_session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, reading_session_id, level, message, created_at
                FROM extraction_logs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    return [dict(row) for row in rows]


def _event_key(sport_name: str, competition_name: Optional[str], event: dict) -> str:
    return "|".join(
        [
            sport_name or "",
            competition_name or "",
            event.get("event_name") or "",
            event.get("start_date") or "",
            event.get("start_time") or "",
        ]
    )


def _decimal_or_none(value: object) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(str(value))
    except ValueError:
        return None


def _ensure_arbitrage_sections(result: dict) -> dict:
    analysis = result.get("section_2_arbitrage_analysis") or {}
    if "section_1_all_available_sporting_events_and_odds" in result and "event_analyses" in analysis:
        return result
    try:
        from .services.arbitrage_service import ArbitrageService

        sections = ArbitrageService().build_sections(result.get("structured_content", {}), result.get("total_stake", 100))
    except Exception:
        return result
    result["total_stake"] = sections["total_stake"]
    result["section_1_all_available_sporting_events_and_odds"] = sections[
        "section_1_all_available_sporting_events_and_odds"
    ]
    result["section_2_arbitrage_analysis"] = sections["section_2_arbitrage_analysis"]
    result["section_3_arbitrage_summary"] = sections["section_3_arbitrage_summary"]
    return result
