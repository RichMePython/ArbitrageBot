from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..config import BROWSER_TIMEOUT_MS, BROWSER_WAIT_MS, MAX_SCROLLS, SCREENSHOT_DIR
from .content_cleaning_service import clean_lines


class BrowserRenderService:
    method_name = "browser_automation"

    async def extract(self, url: str, session_id: str, log: Callable[[str, str], None]) -> dict:
        try:
            from playwright.async_api import TimeoutError as PlaywrightTimeoutError
            from playwright.async_api import async_playwright
        except ModuleNotFoundError:
            warning = "Playwright is not installed. Run python -m pip install -r requirements.txt."
            log("warning", warning)
            return self._failed(warning)

        warnings: list[str] = []
        screenshot_paths: list[str] = []
        all_text_blocks: list[str] = []
        html = ""
        title = None
        dom_blocks: list[dict] = []

        screenshot_dir = Path(SCREENSHOT_DIR) / session_id
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        log("info", "Starting browser automation extraction.")
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page(
                    viewport={"width": 1440, "height": 1200},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36 WebsiteContentReader/1.0"
                    ),
                )
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=BROWSER_TIMEOUT_MS)
                    except PlaywrightTimeoutError:
                        warnings.append("Network idle was not reached before timeout; extraction continued with visible content.")
                    await page.wait_for_timeout(BROWSER_WAIT_MS)
                    title = await page.title()

                    previous_height = 0
                    stable_scrolls = 0
                    for index in range(MAX_SCROLLS):
                        try:
                            body_text = await page.locator("body").inner_text(timeout=10000)
                            all_text_blocks.append(body_text)
                        except PlaywrightTimeoutError:
                            warnings.append("Body text was not available during one browser extraction pass.")

                        if index < 5:
                            screenshot_path = screenshot_dir / f"screenshot_{index + 1}.png"
                            await page.screenshot(path=str(screenshot_path), full_page=False)
                            screenshot_paths.append(str(screenshot_path))

                        page_blocks = await self._collect_visible_blocks(page)
                        dom_blocks.extend(page_blocks)

                        scroll_state = await page.evaluate(
                            """
                            () => {
                              const scrollHeight = Math.max(
                                document.body.scrollHeight,
                                document.documentElement.scrollHeight
                              );
                              const scrollY = window.scrollY || document.documentElement.scrollTop;
                              const innerHeight = window.innerHeight;
                              window.scrollBy(0, Math.floor(innerHeight * 0.85));
                              return { scrollHeight, scrollY, innerHeight };
                            }
                            """
                        )
                        await page.wait_for_timeout(900)

                        height = int(scroll_state.get("scrollHeight") or 0)
                        scroll_y = int(scroll_state.get("scrollY") or 0)
                        inner_height = int(scroll_state.get("innerHeight") or 0)
                        if scroll_y + inner_height >= height - 20:
                            break
                        if height == previous_height:
                            stable_scrolls += 1
                        else:
                            stable_scrolls = 0
                        if stable_scrolls >= 2:
                            break
                        previous_height = height

                    html = await page.content()
                finally:
                    await browser.close()
        except Exception as exc:
            warning = f"Browser automation failed: {exc}"
            if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc).lower():
                warning += " Run python -m playwright install chromium."
            log("warning", warning)
            return self._failed(warning, screenshot_paths=screenshot_paths)

        lines = clean_lines(all_text_blocks)
        block_lines = clean_lines([block.get("text", "") for block in dom_blocks])
        merged_lines = clean_lines([*lines, *block_lines])

        if not merged_lines:
            warnings.append("Browser opened the page, but no visible readable text was extracted.")

        log("info", f"Browser automation extracted {len(merged_lines)} readable text lines.")
        return {
            "success": bool(merged_lines),
            "method": self.method_name,
            "page_title": title,
            "raw_text": merged_lines,
            "html": html,
            "screenshot_paths": screenshot_paths,
            "dom_blocks": dom_blocks,
            "warnings": warnings,
        }

    async def _collect_visible_blocks(self, page) -> list[dict]:
        return await page.evaluate(
            """
            () => {
              const isVisible = (element) => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style &&
                  style.visibility !== 'hidden' &&
                  style.display !== 'none' &&
                  rect.width > 0 &&
                  rect.height > 0;
              };

              const nodes = Array.from(document.querySelectorAll('body *'));
              return nodes
                .filter(isVisible)
                .map((element) => {
                  const rect = element.getBoundingClientRect();
                  const ownText = (element.innerText || element.textContent || '').trim();
                  return {
                    tag: element.tagName.toLowerCase(),
                    role: element.getAttribute('role') || '',
                    aria: element.getAttribute('aria-label') || '',
                    id: element.id || '',
                    className: String(element.className || ''),
                    text: ownText,
                    x: Math.round(rect.x),
                    y: Math.round(rect.y + window.scrollY),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                  };
                })
                .filter((item) => item.text && item.text.length <= 500)
                .slice(0, 1200);
            }
            """
        )

    def _failed(self, warning: str, screenshot_paths: list[str] | None = None) -> dict:
        return {
            "success": False,
            "method": self.method_name,
            "page_title": None,
            "raw_text": [],
            "html": "",
            "screenshot_paths": screenshot_paths or [],
            "dom_blocks": [],
            "warnings": [warning],
        }

