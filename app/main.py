"""FastAPI 앱 — 웹 UI 서빙 + 생성 API."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .models import BatchRequest, BatchResult, GenerationRequest, GenerationResult
from .services import asset_catalog, pipeline, usage


def _slug(text: str) -> str:
    """폴더명에 안전한 슬러그 (한글 허용, 특수문자만 제거)."""
    text = (text or "").strip()
    text = re.sub(r"[^\w가-힣\- ]", "", text).replace(" ", "-")
    return text[:24] or "untitled"


def _job_id(prefix: str, label: str) -> str:
    """읽기 쉬운 폴더명: <prefix>_<label>_<날짜시각>."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}_{_slug(label)}_{ts}"

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
        "output_dir": settings.output_dir,
    }


@app.get("/api/catalog")
def catalog() -> dict:
    """엔티티 타입 + 생성 가능한 에셋 카탈로그."""
    return asset_catalog.catalog_payload()


@app.get("/api/usage")
def get_usage() -> dict:
    """이 앱에서 생성한 사용량 + 예상 비용 (실제 잔액 아님)."""
    return usage.snapshot(settings)


@app.post("/api/usage/reset")
def reset_usage() -> dict:
    usage.reset()
    return usage.snapshot(settings)


@app.post("/api/generate", response_model=GenerationResult)
def generate(req: GenerationRequest) -> GenerationResult:
    label = req.name or req.role or req.entity_type
    job_id = _job_id(req.entity_type, label)
    try:
        result = pipeline.run_pipeline(req, settings, job_id)
    except Exception as exc:  # pragma: no cover - top-level guard
        raise HTTPException(status_code=500, detail=f"생성 실패: {exc}") from exc
    return result


@app.post("/api/generate_batch", response_model=BatchResult)
def generate_batch(req: BatchRequest) -> BatchResult:
    """일괄 생성 — 여러 개체 + 도감 오버뷰."""
    batch_id = _job_id("batch-" + req.entity_type, req.genre)
    try:
        result = pipeline.run_batch(req, settings, batch_id)
    except Exception as exc:  # pragma: no cover - top-level guard
        raise HTTPException(status_code=500, detail=f"일괄 생성 실패: {exc}") from exc
    return result


@app.get("/api/history")
def history(limit: int = 60) -> list[dict]:
    """생성 히스토리 — output 폴더의 result.json 을 스캔해 최신순 목록 반환."""
    import json

    root = settings.output_path
    items = []
    if not root.is_dir():
        return items
    for d in root.iterdir():
        if not d.is_dir():
            continue
        rj = d / "result.json"
        if not rj.exists():
            continue
        try:
            data = json.loads(rj.read_text(encoding="utf-8"))
            mtime = rj.stat().st_mtime
        except Exception:
            continue
        is_batch = "entries" in data or "batch_id" in data
        if is_batch:
            concept0 = (data.get("entries") or [{}])[0].get("concept", {})
            name = f"{data.get('entity_type', '')} 도감 ({len(data.get('entries', []))}종)"
            entity = data.get("entity_type", "")
            thumb = (data.get("codex") or {}).get("path", "")
        else:
            c = data.get("concept", {})
            name = c.get("name", d.name)
            entity = c.get("entity_type", "")
            thumb = next((a["path"] for a in data.get("assets", [])
                          if a.get("is_image") and a.get("category") == "character"), "")
            if not thumb:
                thumb = next((a["path"] for a in data.get("assets", [])
                              if a.get("kind") == "sheet_png"), "")
        items.append({
            "id": d.name, "kind": "batch" if is_batch else "single",
            "name": name, "entity": entity, "thumb": thumb,
            "result_url": f"/files/{d.name}/result.json",
            "mtime": mtime,
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items[:limit]


@app.post("/api/open/{job_id}")
def open_folder(job_id: str) -> dict:
    """로컬 파일 탐색기에서 해당 결과 폴더 열기 (로컬 실행 전용)."""
    import subprocess
    import sys

    safe = Path(job_id).name
    folder = (settings.output_path / safe).resolve()
    if not str(folder).startswith(str(settings.output_path.resolve())) or not folder.is_dir():
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    try:
        if sys.platform.startswith("win"):
            import os
            os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"폴더 열기 실패: {exc}") from exc
    return {"opened": str(folder)}


@app.delete("/api/history/{job_id}")
def delete_history(job_id: str) -> dict:
    """히스토리 항목(폴더) 삭제."""
    import shutil

    safe = Path(job_id).name
    folder = (settings.output_path / safe).resolve()
    if not str(folder).startswith(str(settings.output_path.resolve())) or not folder.is_dir():
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    shutil.rmtree(folder, ignore_errors=True)
    return {"deleted": safe}


@app.get("/api/zip/{job_id}")
def download_zip(job_id: str):
    """잡/배치 폴더 전체를 ZIP 으로 묶어 다운로드."""
    import io
    import zipfile

    from fastapi.responses import StreamingResponse

    safe = Path(job_id).name  # 경로 탐색 방지
    folder = (settings.output_path / safe).resolve()
    if not str(folder).startswith(str(settings.output_path.resolve())) or not folder.is_dir():
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(folder))
    buf.seek(0)
    # 한글 파일명 대응: ASCII 폴백 + RFC5987 UTF-8 파일명
    from urllib.parse import quote
    ascii_name = (safe.encode("ascii", "ignore").decode() or "download").strip("_-") or "download"
    disp = f"attachment; filename=\"{ascii_name}.zip\"; filename*=UTF-8''{quote(safe)}.zip"
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": disp},
    )


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
