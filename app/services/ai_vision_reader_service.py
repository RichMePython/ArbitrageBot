from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Callable

from ..config import AI_VISION_MODEL
from .content_cleaning_service import clean_lines


class AiVisionReaderService:
    method_name = "ai_vision_reader"

    def extract(self, source_url: str, screenshot_paths: list[str], log: Callable[[str, str], None]) -> dict:
        if not screenshot_paths:
            warning = "AI vision reader was skipped because no screenshots were available."
            log("warning", warning)
            return self._failed([warning])

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            warning = "AI vision reader was skipped because OPENAI_API_KEY is not configured."
            log("warning", warning)
            return self._failed([warning], screenshot_paths=screenshot_paths)

        try:
            from openai import OpenAI
        except ModuleNotFoundError:
            warning = "AI vision reader was skipped because the openai package is not installed."
            log("warning", warning)
            return self._failed([warning], screenshot_paths=screenshot_paths)

        log("info", f"Starting AI vision reader on {len(screenshot_paths)} screenshots.")
        prompt = {
            "source_url": source_url,
            "screenshot_paths": [Path(path).name for path in screenshot_paths],
            "task": (
                "Read all visible website content and extract sports, leagues, events, markets, "
                "selections, odds, labels, dates, and times. Return only JSON."
            ),
            "expected_json_shape": {
                "success": True,
                "extraction_method": "ai_vision_reader",
                "visible_text": [],
                "sports": [],
                "events": [],
                "markets": [],
                "odds": [],
                "warnings": [],
                "confidence_score": 0,
            },
        }

        content: list[dict] = [{"type": "text", "text": json.dumps(prompt)}]
        for path in screenshot_paths[:5]:
            image_path = Path(path)
            if not image_path.exists():
                continue
            data = base64.b64encode(image_path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{data}"},
                }
            )

        if len(content) == 1:
            warning = "AI vision reader found no readable screenshot files."
            log("warning", warning)
            return self._failed([warning], screenshot_paths=screenshot_paths)

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=AI_VISION_MODEL,
                messages=[{"role": "user", "content": content}],
                response_format={"type": "json_object"},
                temperature=0,
            )
            payload_text = response.choices[0].message.content or "{}"
            payload = json.loads(payload_text)
        except Exception as exc:
            warning = f"AI vision reader failed: {exc}"
            log("warning", warning)
            return self._failed([warning], screenshot_paths=screenshot_paths)

        visible_text = clean_lines(payload.get("visible_text", []))
        warnings = payload.get("warnings", [])
        return {
            "success": bool(payload.get("success", True) and (visible_text or payload.get("sports"))),
            "method": self.method_name,
            "page_title": None,
            "raw_text": visible_text,
            "structured_ai": payload,
            "screenshot_paths": screenshot_paths,
            "warnings": warnings,
            "confidence_score": int(payload.get("confidence_score") or 0),
        }

    def _failed(self, warnings: list[str], screenshot_paths: list[str] | None = None) -> dict:
        return {
            "success": False,
            "method": self.method_name,
            "page_title": None,
            "raw_text": [],
            "structured_ai": None,
            "screenshot_paths": screenshot_paths or [],
            "warnings": warnings,
            "confidence_score": 0,
        }

