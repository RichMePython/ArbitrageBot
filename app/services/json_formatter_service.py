from __future__ import annotations

from .arbitrage_service import ArbitrageService
from .structured_parser import flatten_events, flatten_odds


class JsonFormatterService:
    def __init__(self) -> None:
        self.arbitrage_service = ArbitrageService()

    def build_result(
        self,
        *,
        session_id: str,
        source_url: str,
        page_title: str | None,
        extraction_method: str,
        timestamp: str,
        confidence_score: int,
        raw_text: list[str],
        structured_content: dict,
        warnings: list[str],
        total_stake: float = 100,
    ) -> dict:
        arbitrage_sections = self.arbitrage_service.build_sections(structured_content, total_stake)
        sports_found = [sport.get("sport_name") for sport in structured_content.get("sports", []) if sport.get("sport_name")]
        events_found = [event.get("event_name") for event in flatten_events(structured_content) if event.get("event_name")]
        odds_found = [
            f"{row.get('selection_name')}: {row.get('odds')}"
            for row in flatten_odds(structured_content)
            if row.get("selection_name") and row.get("odds")
        ]

        summary_lines = [f"Website scanned: {source_url}", "", "Sports found:"]
        summary_lines.extend([f"- {sport}" for sport in sports_found] if sports_found else ["- None identified"])
        summary_lines.extend(["", "Events found:"])
        summary_lines.extend([f"- {event}" for event in events_found[:40]] if events_found else ["- None identified"])
        summary_lines.extend(["", "Odds found:"])
        summary_lines.extend([f"- {odds}" for odds in odds_found[:60]] if odds_found else ["- None identified"])
        summary_lines.extend(
            [
                "",
                f"Extraction method used: {format_method(extraction_method)}",
                f"Confidence: {confidence_score}%",
                f"Total stake for arbitrage: {arbitrage_sections['total_stake']:.2f}",
            ]
        )

        scan_status = "success" if raw_text else "failed"
        if raw_text and confidence_score < 50:
            scan_status = "partial_success"

        return {
            "id": session_id,
            "scan_status": scan_status,
            "source_url": source_url,
            "page_title": page_title,
            "extraction_method": extraction_method,
            "timestamp": timestamp,
            "confidence_score": confidence_score,
            "total_stake": arbitrage_sections["total_stake"],
            "raw_text": raw_text,
            "structured_content": structured_content,
            "section_1_all_available_sporting_events_and_odds": arbitrage_sections[
                "section_1_all_available_sporting_events_and_odds"
            ],
            "section_2_arbitrage_analysis": arbitrage_sections["section_2_arbitrage_analysis"],
            "section_3_arbitrage_summary": arbitrage_sections["section_3_arbitrage_summary"],
            "warnings": warnings,
            "summary": {
                "sports_found": sports_found,
                "events_found": events_found,
                "odds_found": odds_found,
                "summary_text": "\n".join(summary_lines),
            },
        }


def format_method(method: str) -> str:
    return method.replace("_", " ").title()
