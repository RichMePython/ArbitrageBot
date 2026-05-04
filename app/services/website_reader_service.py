from __future__ import annotations

from .ai_vision_reader_service import AiVisionReaderService
from .browser_render_service import BrowserRenderService
from .html_extractor_service import HtmlExtractorService
from .json_formatter_service import JsonFormatterService
from .structured_parser import parse_visible_content, score_extraction
from ..config import FIXED_URL, HTML_MIN_USEFUL_LINES, MIN_CLEAN_CONFIDENCE
from ..storage import complete_session, create_session, fail_session, init_db, log_event, utc_now


class WebsiteReaderService:
    def __init__(self) -> None:
        self.html_extractor = HtmlExtractorService()
        self.browser_renderer = BrowserRenderService()
        self.ai_vision_reader = AiVisionReaderService()
        self.formatter = JsonFormatterService()

    async def read(
        self,
        source_url: str = FIXED_URL,
        initial_warnings: list[str] | None = None,
        total_stake: float = 100,
    ) -> dict:
        init_db()
        session_id = create_session(source_url)
        warnings = list(initial_warnings or [])

        def log(level: str, message: str) -> None:
            log_event(session_id, level, message)

        log("info", f"Reading session started for {source_url}.")

        html_candidate = self.html_extractor.extract(source_url, log)
        html_result = self._candidate_to_result(
            session_id=session_id,
            source_url=source_url,
            candidate=html_candidate,
            inherited_warnings=warnings,
            total_stake=total_stake,
        )

        if self._is_clean_enough(html_result):
            log("info", "HTML extraction was clean enough; browser fallback was not needed.")
            complete_session(session_id, html_result)
            return html_result

        log("info", "HTML extraction was incomplete; trying browser automation.")
        browser_candidate = await self.browser_renderer.extract(source_url, session_id, log)
        browser_result = self._candidate_to_result(
            session_id=session_id,
            source_url=source_url,
            candidate=browser_candidate,
            inherited_warnings=[*warnings, *html_candidate.get("warnings", [])],
            total_stake=total_stake,
        )

        if self._is_clean_enough(browser_result):
            log("info", "Browser automation produced structured content.")
            complete_session(session_id, browser_result)
            return browser_result

        screenshot_paths = browser_candidate.get("screenshot_paths", [])
        if screenshot_paths:
            log("info", "Browser extraction was incomplete; trying AI vision reader.")
            ai_candidate = self.ai_vision_reader.extract(source_url, screenshot_paths, log)
            ai_result = self._ai_candidate_to_result(
                session_id=session_id,
                source_url=source_url,
                ai_candidate=ai_candidate,
                fallback_result=browser_result if browser_result.get("raw_text") else html_result,
                total_stake=total_stake,
            )
            if ai_result.get("raw_text") or ai_result.get("structured_content", {}).get("sports"):
                complete_session(session_id, ai_result)
                return ai_result
            warnings.extend(ai_candidate.get("warnings", []))
        else:
            warnings.append("Browser screenshots were not available for AI vision fallback.")

        best_result = browser_result if len(browser_result.get("raw_text", [])) >= len(html_result.get("raw_text", [])) else html_result
        if best_result.get("raw_text"):
            best_result["warnings"] = _dedupe([*best_result.get("warnings", []), *warnings])
            best_result["scan_status"] = "partial_success"
            complete_session(session_id, best_result)
            return best_result

        failure_warnings = _dedupe([*warnings, *html_candidate.get("warnings", []), *browser_candidate.get("warnings", [])])
        log("error", "No readable content could be extracted.")
        return fail_session(session_id, source_url, failure_warnings)

    def _candidate_to_result(
        self,
        *,
        session_id: str,
        source_url: str,
        candidate: dict,
        inherited_warnings: list[str],
        total_stake: float,
    ) -> dict:
        method = candidate.get("method", "unknown")
        raw_text = candidate.get("raw_text", [])
        page_title = candidate.get("page_title")
        structured = parse_visible_content(raw_text, source_url, page_title)
        warnings = _dedupe([*inherited_warnings, *candidate.get("warnings", []), *structured.get("warnings", [])])
        confidence = score_extraction(method, raw_text, structured, warnings)
        return self.formatter.build_result(
            session_id=session_id,
            source_url=source_url,
            page_title=page_title,
            extraction_method=method,
            timestamp=utc_now(),
            confidence_score=confidence,
            raw_text=raw_text,
            structured_content=structured,
            warnings=warnings,
            total_stake=total_stake,
        )

    def _ai_candidate_to_result(
        self,
        *,
        session_id: str,
        source_url: str,
        ai_candidate: dict,
        fallback_result: dict,
        total_stake: float,
    ) -> dict:
        if not ai_candidate.get("success"):
            return fallback_result

        payload = ai_candidate.get("structured_ai") or {}
        raw_text = ai_candidate.get("raw_text") or payload.get("visible_text") or fallback_result.get("raw_text", [])
        structured = self._coerce_ai_structured_content(payload)
        if not structured.get("sports"):
            structured = parse_visible_content(raw_text, source_url, fallback_result.get("page_title"))

        warnings = _dedupe(
            [
                *fallback_result.get("warnings", []),
                "AI reader was used because normal HTML or browser extraction was incomplete.",
                *ai_candidate.get("warnings", []),
                *structured.get("warnings", []),
            ]
        )
        confidence = int(ai_candidate.get("confidence_score") or 0)
        if confidence <= 0:
            confidence = score_extraction("ai_vision_reader", raw_text, structured, warnings)

        return self.formatter.build_result(
            session_id=session_id,
            source_url=source_url,
            page_title=fallback_result.get("page_title"),
            extraction_method="ai_vision_reader",
            timestamp=utc_now(),
            confidence_score=confidence,
            raw_text=raw_text,
            structured_content=structured,
            warnings=warnings,
            total_stake=total_stake,
        )

    def _coerce_ai_structured_content(self, payload: dict) -> dict:
        sports = payload.get("sports") or []
        if isinstance(sports, dict):
            sports = [sports]

        normalized_sports: list[dict] = []
        for sport in sports:
            if not isinstance(sport, dict):
                continue
            sport_name = sport.get("sport_name") or sport.get("sport") or sport.get("name") or "Unknown sport"
            competitions = sport.get("competitions") or sport.get("leagues") or []
            if isinstance(competitions, dict):
                competitions = [competitions]
            normalized_competitions = []
            for competition in competitions:
                if not isinstance(competition, dict):
                    continue
                competition_name = (
                    competition.get("competition_name")
                    or competition.get("league")
                    or competition.get("name")
                    or "Unspecified competition"
                )
                events = competition.get("events") or []
                normalized_competitions.append(
                    {
                        "competition_name": competition_name,
                        "events": [event for event in events if isinstance(event, dict)],
                    }
                )
            normalized_sports.append({"sport_name": sport_name, "competitions": normalized_competitions})

        return {
            "sports": normalized_sports,
            "page_sections": payload.get("page_sections") or [],
            "labels": payload.get("labels") or payload.get("visible_labels") or [],
            "warnings": payload.get("warnings") or [],
        }

    def _is_clean_enough(self, result: dict) -> bool:
        raw_count = len(result.get("raw_text", []))
        confidence = int(result.get("confidence_score", 0))
        structured = result.get("structured_content", {})
        sports = structured.get("sports", [])
        has_events = any(
            competition.get("events")
            for sport in sports
            for competition in sport.get("competitions", [])
        )
        has_odds = any(
            selection.get("odds")
            for sport in sports
            for competition in sport.get("competitions", [])
            for event in competition.get("events", [])
            for market in event.get("markets", [])
            for selection in market.get("selections", [])
        )
        return raw_count >= HTML_MIN_USEFUL_LINES and confidence >= MIN_CLEAN_CONFIDENCE and has_events and has_odds


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output
