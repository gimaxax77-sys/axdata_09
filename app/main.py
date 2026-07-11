"""FastAPI 앱 — 웹 UI 서빙 + 생성 API."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .models import CharacterRequest, GenerationResult
from .services import pipeline

settings = get_settings()

app = FastAPI(
    title="AXData Character & Game Art Studio",
    description="GPT + Gemini + CapCut 캐릭터/게임 아트 자동 제작 툴",
    version="0.1.0",
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# 생성 결과물 정적 서빙
app.mount(
    "/files",
    StaticFiles(directory=str(settings.output_path)),
    name="files",
)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/api/status")
def status() -> dict:
    """프론트엔드가 어떤 모드로 동작하는지 표시하기 위한 상태."""
    return {
        "gpt": "live" if settings.gpt_enabled else "demo",
        "gemini": "live" if settings.gemini_enabled else "demo",
        "openai_model": settings.openai_model,
        "gemini_model": settings.gemini_image_model,
    }


@app.post("/api/generate", response_model=GenerationResult)
def generate(req: CharacterRequest) -> GenerationResult:
    job_id = uuid.uuid4().hex[:12]
    try:
        result = pipeline.run_pipeline(req, settings, job_id)
    except Exception as exc:  # pragma: no cover - top-level guard
        raise HTTPException(status_code=500, detail=f"생성 실패: {exc}") from exc
    return result


@app.get("/api/download/{job_id}/{filename}")
def download(job_id: str, filename: str) -> FileResponse:
    """산출물 다운로드 (경로 탐색 방지)."""
    safe = Path(filename).name
    path = (settings.output_path / job_id / safe).resolve()
    if not str(path).startswith(str(settings.output_path.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=safe)


# 정적 자산 (JS/CSS) — 마지막에 마운트해 API 라우트가 우선하도록
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
