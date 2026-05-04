import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "reader.sqlite3"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
STATIC_DIR = BASE_DIR / "app" / "static"

FIXED_URL = "https://betting.co.zw/sportsbook/upcoming"

REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "45000"))
BROWSER_WAIT_MS = int(os.getenv("BROWSER_WAIT_MS", "2500"))
MAX_SCROLLS = int(os.getenv("MAX_SCROLLS", "8"))

HTML_MIN_USEFUL_LINES = int(os.getenv("HTML_MIN_USEFUL_LINES", "15"))
MIN_CLEAN_CONFIDENCE = int(os.getenv("MIN_CLEAN_CONFIDENCE", "72"))

AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", "gpt-4o-mini")

