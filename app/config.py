import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"


def is_serverless_runtime(base_dir: Path = BASE_DIR, env: dict | None = None) -> bool:
    values = env if env is not None else os.environ
    base_text = str(base_dir).replace("\\", "/")
    return (
        base_text.startswith("/var/task")
        or bool(values.get("AWS_LAMBDA_FUNCTION_NAME"))
        or bool(values.get("LAMBDA_TASK_ROOT"))
        or bool(values.get("VERCEL"))
    )


def resolve_data_dir(base_dir: Path = BASE_DIR, env: dict | None = None) -> Path:
    values = env if env is not None else os.environ
    configured_dir = values.get("DATA_DIR")
    if configured_dir:
        return Path(configured_dir)

    if is_serverless_runtime(base_dir, values):
        return Path(values.get("TMPDIR", "/tmp")) / "arbitragebot" / "data"

    return base_dir / "data"


def resolve_playwright_browsers_path(base_dir: Path = BASE_DIR, env: dict | None = None) -> Path | None:
    values = env if env is not None else os.environ
    configured_path = values.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured_path:
        return Path(configured_path)
    if is_serverless_runtime(base_dir, values):
        return base_dir / "app" / "playwright-browsers"
    return None


DATA_DIR = resolve_data_dir()
DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "reader.sqlite3")))
SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", str(DATA_DIR / "screenshots")))
PLAYWRIGHT_BROWSERS_PATH = resolve_playwright_browsers_path()
if PLAYWRIGHT_BROWSERS_PATH:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PLAYWRIGHT_BROWSERS_PATH))
    os.environ.setdefault("PLAYWRIGHT_SKIP_BROWSER_GC", "1")

FIXED_URL = "https://betting.co.zw/sportsbook/upcoming"

REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
BROWSER_TIMEOUT_MS = int(os.getenv("BROWSER_TIMEOUT_MS", "45000"))
BROWSER_WAIT_MS = int(os.getenv("BROWSER_WAIT_MS", "2500"))
MAX_SCROLLS = int(os.getenv("MAX_SCROLLS", "8"))

HTML_MIN_USEFUL_LINES = int(os.getenv("HTML_MIN_USEFUL_LINES", "15"))
MIN_CLEAN_CONFIDENCE = int(os.getenv("MIN_CLEAN_CONFIDENCE", "72"))

AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", "gpt-4o-mini")
