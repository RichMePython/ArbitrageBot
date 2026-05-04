from __future__ import annotations

from typing import Callable

import requests
from bs4 import BeautifulSoup

from ..config import REQUEST_TIMEOUT_SECONDS
from .content_cleaning_service import clean_lines


class HtmlExtractorService:
    method_name = "html_extraction"

    def extract(self, url: str, log: Callable[[str, str], None]) -> dict:
        log("info", "Starting normal HTML extraction.")
        warnings: list[str] = []
        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36 WebsiteContentReader/1.0"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            warning = f"HTML extraction request failed: {exc}"
            log("warning", warning)
            return {
                "success": False,
                "method": self.method_name,
                "page_title": None,
                "raw_text": [],
                "html": "",
                "warnings": [warning],
            }

        soup = BeautifulSoup(response.text, "html.parser")
        for element in soup(["script", "style", "noscript", "svg", "canvas"]):
            element.decompose()

        title = soup.title.get_text(" ", strip=True) if soup.title else None
        body = soup.body or soup
        text = body.get_text("\n", strip=True)
        lines = clean_lines(text)

        if not lines:
            warnings.append("HTML loaded, but no visible body text was found.")

        log("info", f"HTML extraction found {len(lines)} readable text lines.")
        return {
            "success": bool(lines),
            "method": self.method_name,
            "page_title": title,
            "raw_text": lines,
            "html": response.text,
            "warnings": warnings,
        }

