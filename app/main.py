from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import FIXED_URL, STATIC_DIR
from .services.website_reader_service import WebsiteReaderService
from .storage import get_logs, get_session_result, init_db, list_sessions


class ScanRequest(BaseModel):
    url: Optional[str] = None
    total_stake: Optional[float] = 100


app = FastAPI(
    title="Website Content Reader",
    version="1.0.0",
    description="Read-only extractor for visible sportsbook page contents.",
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/reader")


@app.post("/api/scan")
async def scan(payload: Optional[ScanRequest] = None) -> dict:
    requested_url = payload.url if payload else None
    warnings: list[str] = []
    if requested_url and requested_url != FIXED_URL:
        warnings.append("Only the fixed configured URL can be scanned; the submitted URL was ignored.")

    service = WebsiteReaderService()
    total_stake = payload.total_stake if payload and payload.total_stake and payload.total_stake > 0 else 100
    result = await service.read(FIXED_URL, initial_warnings=warnings, total_stake=total_stake)
    return result


@app.get("/api/config")
def read_config() -> dict:
    return {"fixed_url": FIXED_URL}


@app.get("/api/sessions")
def read_sessions(limit: int = 25) -> list[dict]:
    return list_sessions(limit=limit)


@app.get("/api/sessions/latest")
def read_latest_session() -> dict:
    result = get_session_result("latest")
    if not result:
        raise HTTPException(status_code=404, detail="No reading sessions found.")
    return result


@app.get("/api/sessions/{session_id}")
def read_session(session_id: str) -> dict:
    result = get_session_result(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reading session not found.")
    return result


@app.get("/api/logs")
def read_logs(session_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    return get_logs(session_id=session_id, limit=limit)


def _spa_index() -> FileResponse:
    index_file = Path(STATIC_DIR) / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend has not been built yet. Run npm.cmd install and npm.cmd run build in ./frontend.",
        )
    return FileResponse(index_file)


@app.get("/reader", include_in_schema=False)
def reader_page() -> FileResponse:
    return _spa_index()


@app.get("/results", include_in_schema=False)
def results_page() -> FileResponse:
    return _spa_index()


@app.get("/arbitrage", include_in_schema=False)
def arbitrage_page() -> FileResponse:
    return _spa_index()


@app.get("/logs", include_in_schema=False)
def logs_page() -> FileResponse:
    return _spa_index()
