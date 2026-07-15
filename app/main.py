"""FastAPI 앱 — 웹 UI 서빙 + 생성 API."""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .logging_config import get_logger, setup_logging
from .models import (
    BatchRequest,
    BatchResult,
    EditRequest,
    GenerationRequest,
    GenerationResult,
    ImportRunRequest,
    RegenerateRequest,
    RepackRequest,
)
from .services import asset_catalog, pipeline, progress, usage

setup_logging()
log = get_logger(__name__)


def _safe_path(root: Path, *parts: str) -> Path:
    """root 하위로만 해석되는 안전한 경로. 벗어나면 404."""
    full = (root.joinpath(*parts)).resolve()
    root = root.resolve()
    if full != root and root not in full.parents:
        raise HTTPException(status_code=404, detail="경로를 찾을 수 없습니다.")
    return full


def _safe_job(job_id: str) -> str:
    """중첩 job 경로(대분류/중분류/폴더)를 output 하위로 검증하고 상대경로 반환."""
    full = _safe_path(settings.output_path, job_id)
    return full.relative_to(settings.output_path.resolve()).as_posix()


def _require_local(request: Request) -> None:
    """PC 로컬(루프백)에서만 허용 — LAN(0.0.0.0) 노출 시 제어 엔드포인트 보호."""
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403,
                            detail="이 기능은 서버가 실행 중인 PC에서만 사용할 수 있습니다.")


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

log.info("AXData Studio 시작 — GPT:%s Gemini:%s output=%s",
         "live" if settings.gpt_enabled else "demo",
         "live" if settings.gemini_enabled else "demo",
         settings.output_dir)


@app.get("/files/{path:path}")
def serve_output(path: str) -> FileResponse:
    """생성 결과물 서빙 (현재 output_dir 를 요청 시점에 읽어 동적 서빙)."""
    full = _safe_path(settings.output_path, path)
    if not full.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(full)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    # 캐시 무효화: app.js/style.css 수정시각을 ?v= 버전으로 주입해, 업데이트 후
    # 브라우저가 예전 파일을 캐시에서 쓰지 않고 항상 최신을 받도록 한다.
    try:
        ver = int(max((STATIC_DIR / f).stat().st_mtime for f in ("app.js", "style.css")))
    except OSError:
        ver = 0
    html = (html.replace('src="/app.js"', f'src="/app.js?v={ver}"')
                .replace('href="/style.css"', f'href="/style.css?v={ver}"'))
    return HTMLResponse(html)


@app.get("/api/status")
def status() -> dict:
    """프론트엔드가 어떤 모드로 동작하는지 표시하기 위한 상태."""
    return {
        "gpt": "live" if settings.gpt_enabled else "demo",
        "gemini": "live" if settings.gemini_enabled else "demo",
        "openai_model": settings.openai_model,
        "gemini_model": settings.gemini_image_model,
        "output_dir": settings.output_dir,
        "pricing": {
            "gemini_image": settings.gemini_price_image,
            "openai_image": settings.openai_image_price,
            "gpt_concept": settings.gpt_concept_cost,
            "usd_krw": settings.usd_krw,
        },
    }


@app.get("/api/catalog")
def catalog() -> dict:
    """엔티티 타입 + 생성 가능한 에셋 카탈로그."""
    return asset_catalog.catalog_payload()


@app.get("/api/settings")
def get_settings_api() -> dict:
    """현재 저장 경로 등 설정."""
    return {
        "output_dir": settings.output_dir,
        "output_abs": str(settings.output_path.resolve()),
    }


@app.post("/api/settings")
def set_settings_api(payload: dict, request: Request) -> dict:
    """저장 경로(output_dir) 변경 → 영속화 + 즉시 반영. (로컬 전용)"""
    _require_local(request)
    from . import runtime

    new_dir = (payload or {}).get("output_dir", "").strip()
    if not new_dir:
        raise HTTPException(status_code=400, detail="경로가 비어 있습니다.")
    try:
        p = Path(new_dir).expanduser()
        p.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"경로 생성 실패: {exc}") from exc
    runtime.set_output_dir(str(p))
    settings.output_dir = str(p)  # 캐시된 settings 즉시 갱신
    return {"output_dir": settings.output_dir, "output_abs": str(settings.output_path.resolve())}


@app.get("/api/presets")
def list_presets() -> dict:
    from . import runtime
    return runtime.get_presets()


@app.post("/api/presets")
def save_preset_api(payload: dict, request: Request) -> dict:
    _require_local(request)
    from . import runtime
    name = (payload or {}).get("name", "").strip()
    config = (payload or {}).get("config")
    if not name or config is None:
        raise HTTPException(status_code=400, detail="name/config 가 필요합니다.")
    runtime.save_preset(name, config)
    return {"saved": name, "presets": runtime.get_presets()}


@app.delete("/api/presets/{name}")
def delete_preset_api(name: str, request: Request) -> dict:
    _require_local(request)
    from . import runtime
    runtime.delete_preset(name)
    return {"deleted": name, "presets": runtime.get_presets()}


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


@app.get("/api/budget")
def get_budget_api() -> dict:
    """예산·비용 상한 설정 + 이번 달 실지출 누적."""
    from . import runtime
    month = _current_month()
    return {
        "limits": runtime.get_budget(),
        "month": month,
        "month_spent_usd": round(runtime.get_month_spend(month), 4),
        "usd_krw": settings.usd_krw,
    }


@app.post("/api/budget")
def set_budget_api(payload: dict, request: Request) -> dict:
    """예산 상한 설정 변경 (로컬 전용)."""
    _require_local(request)
    from . import runtime
    limits = runtime.set_budget((payload or {}).get("limits") or payload or {})
    month = _current_month()
    return {"limits": limits, "month": month,
            "month_spent_usd": round(runtime.get_month_spend(month), 4),
            "usd_krw": settings.usd_krw}


def _record_spend(before_usd: float) -> None:
    """생성 전후 usage 총액 차이를 이번 달 지출로 누적 (데모=0 이면 무시)."""
    from . import runtime
    after = usage.snapshot(settings)["total_usd"]
    runtime.add_spend(_current_month(), max(0.0, after - before_usd))


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
    before = usage.snapshot(settings)["total_usd"]
    try:
        result = pipeline.run_pipeline(req, settings, job_id)
        _record_spend(before)
    except progress.Cancelled as exc:
        _record_spend(before)
        progress.finish(req.progress_id, error="취소됨")
        raise HTTPException(status_code=409, detail="생성이 취소되었습니다.") from exc
    except Exception as exc:  # pragma: no cover - top-level guard
        progress.finish(req.progress_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"생성 실패: {exc}") from exc
    return result


@app.post("/api/generate_batch", response_model=BatchResult)
def generate_batch(req: BatchRequest) -> BatchResult:
    """일괄 생성 — 여러 개체 + 도감 오버뷰."""
    batch_id = _job_id("batch-" + req.entity_type, req.genre)
    before = usage.snapshot(settings)["total_usd"]
    try:
        result = pipeline.run_batch(req, settings, batch_id)
        _record_spend(before)
    except progress.Cancelled as exc:
        _record_spend(before)
        progress.finish(req.progress_id, error="취소됨")
        raise HTTPException(status_code=409, detail="일괄 생성이 취소되었습니다.") from exc
    except Exception as exc:  # pragma: no cover - top-level guard
        progress.finish(req.progress_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"일괄 생성 실패: {exc}") from exc
    return result


@app.post("/api/regenerate/{job_id:path}")
def regenerate(job_id: str, req: RegenerateRequest) -> dict:
    """기존 잡의 특정 이미지 에셋 하나만 다시 생성."""
    safe = _safe_job(job_id)
    before = usage.snapshot(settings)["total_usd"]
    try:
        assets = pipeline.regenerate_asset(req, settings, safe)
        _record_spend(before)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - top-level guard
        raise HTTPException(status_code=500, detail=f"재생성 실패: {exc}") from exc
    # 히스토리 캐시 무효화(result.json 변경됨)
    _HISTORY_CACHE.pop(str(settings.output_path / safe / "result.json"), None)
    return {"job_id": safe, "assets": [a.model_dump() for a in assets]}


@app.post("/api/repack/{job_id:path}")
def repack_asset(job_id: str, req: RepackRequest) -> dict:
    """여러 변형 중 선택한 것만 남기고 시트를 재패킹."""
    safe = _safe_job(job_id)
    try:
        out = pipeline.repack_variants(req, settings, safe)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - top-level guard
        raise HTTPException(status_code=500, detail=f"재패킹 실패: {exc}") from exc
    _HISTORY_CACHE.pop(str(settings.output_path / safe / "result.json"), None)
    return {"job_id": safe, **out}


@app.post("/api/edit/{job_id:path}")
def edit_asset(job_id: str, req: EditRequest) -> dict:
    """기존 잡의 이미지 파일 하나를 편집(크롭/배경/보정)해 제자리 저장."""
    from .services import editor

    safe_job = _safe_job(job_id)
    fname = Path(req.file).name  # 경로 탐색 방지
    target = _safe_path(settings.output_path, safe_job, fname)
    if not target.is_file() or target.suffix.lower() != ".png":
        raise HTTPException(status_code=404, detail="이미지 파일을 찾을 수 없습니다.")
    try:
        size = editor.apply_edit(
            target, crop=req.crop, bg=req.bg,
            brightness=req.brightness, contrast=req.contrast, saturation=req.saturation,
        )
    except Exception as exc:  # pragma: no cover - top-level guard
        raise HTTPException(status_code=500, detail=f"편집 실패: {exc}") from exc
    rel = f"{safe_job}/{fname}"
    return {"file": rel, "width": size[0], "height": size[1]}


@app.get("/api/template.csv")
def import_template() -> PlainTextResponse:
    """아트 제작 표준 양식 CSV 다운로드."""
    from .services import importer
    from urllib.parse import quote
    disp = ("attachment; filename=\"axdata_template.csv\"; "
            "filename*=UTF-8''" + quote("아트제작_표준양식.csv"))
    return PlainTextResponse(
        importer.TEMPLATE_CSV, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": disp},
    )


@app.post("/api/import/preview")
async def import_preview(file: UploadFile = File(...)) -> dict:
    """CSV/스프레드시트를 분석해 생성 계획(미리보기)을 반환. 생성은 하지 않음."""
    from .services import importer

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(content) > 5 * 1024 * 1024:  # 5MB 상한 (표는 최대 50행)
        raise HTTPException(status_code=400, detail="파일이 너무 큽니다(최대 5MB).")
    try:
        rows = importer.parse_upload(file.filename or "", content)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"파일 분석 실패: {exc}") from exc
    if not rows:
        raise HTTPException(status_code=400, detail="유효한 데이터 행을 찾지 못했습니다. "
                            "표준 양식을 사용했는지 확인하세요.")
    return importer.analyze(rows)


@app.post("/api/import/run")
def import_run(payload: ImportRunRequest) -> dict:
    """분석된 개체 목록을 일괄 생성 (각 행 = 독립 잡)."""
    rows = payload.rows[:50]
    if not rows:
        raise HTTPException(status_code=400, detail="생성할 행이 없습니다.")
    job_ids = [f"{_job_id(r.entity_type, r.name or r.role or r.entity_type)}_{i}"
               for i, r in enumerate(rows)]
    before = usage.snapshot(settings)["total_usd"]
    try:
        results = pipeline.run_import(rows, settings, job_ids, payload.progress_id)
        _record_spend(before)
    except progress.Cancelled as exc:
        _record_spend(before)
        raise HTTPException(status_code=409, detail="CSV 생성이 취소되었습니다.") from exc
    except Exception as exc:  # pragma: no cover - top-level guard
        _record_spend(before)
        raise HTTPException(status_code=500, detail=f"CSV 생성 실패: {exc}") from exc
    return {"count": len(results),
            "results": [r.model_dump() for r in results]}


@app.get("/api/progress/{progress_id}")
def get_progress(progress_id: str) -> dict:
    """생성 진행률 조회 (프론트 폴링용)."""
    snap = progress.snapshot(progress_id)
    if snap is None:
        return {"found": False}
    pct = int(snap["current"] / max(1, snap["total"]) * 100)
    return {"found": True, "percent": pct, **snap}


@app.post("/api/cancel/{progress_id}")
def cancel_progress(progress_id: str) -> dict:
    """진행 중인 생성 취소 요청."""
    ok = progress.cancel(progress_id)
    return {"cancelled": ok}


# 히스토리 항목 캐시: result.json 절대경로 → (mtime, 파싱된 항목 dict).
# 폴더 스캔은 매번 하되(가벼움), 변경되지 않은 result.json 은 재파싱하지 않는다.
_HISTORY_CACHE: dict[str, tuple[float, dict]] = {}


def _history_item(d: Path) -> dict | None:
    """폴더 하나의 result.json 을 히스토리 항목으로 변환(캐시 사용)."""
    import json

    rj = d / "result.json"
    try:
        mtime = rj.stat().st_mtime
    except OSError:
        return None
    key = str(rj)
    cached = _HISTORY_CACHE.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        data = json.loads(rj.read_text(encoding="utf-8"))
    except Exception:
        return None
    rel = d.relative_to(settings.output_path).as_posix()  # 중첩 경로(대분류/중분류/폴더)
    is_batch = "entries" in data or "batch_id" in data
    if is_batch:
        name = f"{data.get('entity_type', '')} 도감 ({len(data.get('entries', []))}종)"
        entity = data.get("entity_type", "")
        thumb = (data.get("codex") or {}).get("path", "")
    else:
        c = data.get("concept", {})
        name = c.get("name", d.name)
        entity = c.get("entity_type", "")
        thumb = next((a["path"] for a in data.get("assets", [])
                      if a.get("is_image") and a.get("category") == "character"), "")
        if not thumb:  # 사물/디자인 대상: 캐릭터 아트가 없으니 첫 이미지 산출물
            thumb = next((a["path"] for a in data.get("assets", [])
                          if a.get("is_image") and a.get("kind") not in ("sheet_png", "video")), "")
        if not thumb:
            thumb = next((a["path"] for a in data.get("assets", [])
                          if a.get("kind") == "sheet_png"), "")
    item = {
        "id": rel, "kind": "batch" if is_batch else "single",
        "name": name, "entity": entity, "thumb": thumb,
        "result_url": f"/files/{rel}/result.json",
        "mtime": mtime,
    }
    _HISTORY_CACHE[key] = (mtime, item)
    return item


@app.get("/api/history")
def history(limit: int = 60) -> list[dict]:
    """생성 히스토리 — output 폴더의 result.json 을 스캔해 최신순 목록 반환."""
    root = settings.output_path
    items: list[dict] = []
    if not root.is_dir():
        return items
    seen: set[str] = set()
    # 중첩 폴더(대분류/중분류/잡) 어디에 있든 result.json 을 모두 스캔
    for rj in root.rglob("result.json"):
        item = _history_item(rj.parent)
        if item is None:
            continue
        seen.add(str(rj))
        items.append(item)
    # 삭제된 폴더의 캐시 엔트리 정리
    for stale in [k for k in _HISTORY_CACHE if k not in seen]:
        _HISTORY_CACHE.pop(stale, None)
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items[:limit]


@app.post("/api/open/{job_id:path}")
def open_folder(job_id: str, request: Request) -> dict:
    """로컬 파일 탐색기에서 해당 결과 폴더 열기 (로컬 실행 전용)."""
    _require_local(request)
    import subprocess
    import sys

    folder = _safe_path(settings.output_path, job_id)
    if not folder.is_dir():
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


@app.delete("/api/history/{job_id:path}")
def delete_history(job_id: str) -> dict:
    """히스토리 항목(폴더) 삭제."""
    import shutil

    folder = _safe_path(settings.output_path, job_id)
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    shutil.rmtree(folder, ignore_errors=True)
    return {"deleted": _safe_job(job_id)}


@app.get("/api/zip/{job_id:path}")
def download_zip(job_id: str):
    """잡/배치 폴더 전체를 ZIP 으로 묶어 다운로드."""
    import io
    import zipfile

    from fastapi.responses import StreamingResponse

    folder = _safe_path(settings.output_path, job_id)  # 경로 탐색 방지
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    safe = folder.name  # ZIP 파일명(마지막 폴더명)

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


@app.get("/api/download/{job_id:path}/{filename}")
def download(job_id: str, filename: str) -> FileResponse:
    """산출물 다운로드 (경로 탐색 방지)."""
    safe = Path(filename).name
    path = _safe_path(settings.output_path, job_id, safe)
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(path, filename=safe)


# 정적 자산 (JS/CSS) — 마지막에 마운트해 API 라우트가 우선하도록
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
