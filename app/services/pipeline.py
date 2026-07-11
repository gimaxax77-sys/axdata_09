"""파이프라인 오케스트레이션.

요청 → GPT 기획 → (선택 에셋별) Gemini 아트 → 시트 조합 → CapCut/영상
순으로 실행하고, 생성된 산출물 목록을 반환한다.
"""
from __future__ import annotations

from pathlib import Path

import random
from concurrent.futures import ThreadPoolExecutor

from ..config import Settings
from ..models import (
    BatchRequest,
    BatchResult,
    GeneratedAsset,
    GenerationRequest,
    GenerationResult,
)
from . import asset_catalog as cat
from . import (
    capcut_service,
    codex_composer,
    gemini_service,
    gpt_service,
    sheet_composer,
)


def run_pipeline(req: GenerationRequest, settings: Settings, job_id: str) -> GenerationResult:
    job_dir = settings.output_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    entity = req.entity_type if req.entity_type in cat.ENTITY_TYPES else "character"
    warnings: list[str] = []
    assets: list[GeneratedAsset] = []

    def rel(p: Path) -> str:
        return str(p.relative_to(settings.output_path))

    # 선택 에셋 정규화 (엔티티에 유효한 것만, 기본값 폴백)
    valid = {s.key for s in cat.specs_for_entity(entity)}
    selected = [k for k in req.assets if k in valid] or cat.default_keys(entity)

    # 1) GPT — 기획서
    concept = gpt_service.generate_concept(req, settings)
    if not settings.gpt_enabled:
        warnings.append("OPENAI_API_KEY 미설정 — 기획은 데모 생성기로 만들어졌습니다.")
    (job_dir / "concept.json").write_text(
        concept.model_dump_json(indent=2), encoding="utf-8"
    )

    # 2) 이미지 에셋 생성 (선택된 것만)
    image_map: dict[str, Path] = {}  # 시트/영상에서 재사용할 대표 이미지
    demo_art = False
    for key in selected:
        spec = cat.CATALOG[key]
        if not spec.is_image:
            continue
        for res in gemini_service.generate_asset(spec, concept, job_dir, settings,
                                                 scale=req.image_scale,
                                                 variant_count=req.variant_count):
            image_map.setdefault(key, res.path)  # 첫 변형을 대표로
            if res.demo:
                demo_art = True
            assets.append(GeneratedAsset(
                kind=key, category=spec.category, path=rel(res.path),
                label=res.label, demo=res.demo, is_image=True,
            ))
    if demo_art and not settings.gemini_enabled:
        warnings.append("GEMINI_API_KEY 미설정 — 아트는 데모 플레이스홀더로 생성되었습니다.")

    # 시트/영상에 쓸 대표 이미지 3종 선별
    picks = _pick_images(image_map)

    # 3) 캐릭터 시트 (PNG + PDF)
    if "sheet" in selected:
        png = job_dir / "character_sheet.png"
        pdf = job_dir / "character_sheet.pdf"
        sheet_composer.compose_sheet(concept, picks, png, pdf)
        assets.append(GeneratedAsset(kind="sheet_png", category="composite",
                                     path=rel(png), label="캐릭터 시트 (PNG)",
                                     demo=demo_art, is_image=True))
        assets.append(GeneratedAsset(kind="sheet_pdf", category="composite",
                                     path=rel(pdf), label="캐릭터 시트 (PDF)",
                                     demo=demo_art, is_image=False))

    # 4) CapCut draft + 미리보기 영상
    if "video" in selected and picks:
        storyboard = capcut_service.build_storyboard(concept, picks)
        draft_dir = job_dir / "capcut_draft"
        _, native = capcut_service.build_capcut_draft(concept, picks, draft_dir, storyboard)
        assets.append(GeneratedAsset(
            kind="capcut_draft", category="composite", path=rel(draft_dir),
            label="CapCut 프로젝트" + ("" if native else " (스토리보드)"),
            demo=not native, is_image=False,
        ))
        if not native:
            warnings.append(
                "CapCut 네이티브 draft 는 pyJianYingDraft 설치 시 생성됩니다 — "
                "현재는 스토리보드 JSON + 에셋 + 안내가 제공됩니다."
            )
        gif = job_dir / "showcase.gif"
        mp4 = job_dir / "showcase.mp4"
        _, mp4_out = capcut_service.build_preview_video(concept, picks, storyboard, gif, mp4)
        assets.append(GeneratedAsset(kind="video", category="composite", path=rel(gif),
                                     label="쇼케이스 미리보기 (GIF)", demo=demo_art,
                                     is_image=True))
        if mp4_out:
            assets.append(GeneratedAsset(kind="video", category="composite",
                                         path=rel(mp4_out), label="쇼케이스 영상 (MP4)",
                                         demo=demo_art, is_image=False))

    return GenerationResult(job_id=job_id, concept=concept, assets=assets, warnings=warnings)


_FALLBACK_ROLES = {
    "character": ["전사", "마법사", "궁수", "도적", "성기사", "정찰병", "해커", "파일럿"],
    "monster": ["드래곤", "골렘", "언데드", "거대 늑대", "슬라임", "정령", "키메라", "리치"],
    "npc": ["상인", "대장장이", "여관 주인", "사제", "정보상", "경비병", "학자", "음유시인"],
}

# 데모 모드 일괄 생성 시 개체 이름 중복을 피하기 위한 고유 이름 풀(엔티티별 8개+)
_BATCH_NAMES = {
    "character": ["카엘", "세라핀", "루멘", "녹스", "아리아", "제로", "바이런", "이리스"],
    "monster": ["그림", "발록", "누리스", "카론", "벨제", "라우", "모르가", "제피르"],
    "npc": ["바르트", "미라", "톰슨", "엘리사", "고든", "네리", "오딘", "실비아"],
}


def run_batch(req: BatchRequest, settings: Settings, batch_id: str) -> BatchResult:
    """여러 개체를 한 번에 생성하고 도감 오버뷰를 만든다."""
    entity = req.entity_type if req.entity_type in cat.ENTITY_TYPES else "character"
    count = max(1, min(8, req.count))
    roles_pool = _FALLBACK_ROLES.get(entity, _FALLBACK_ROLES["character"])

    name_pool = _BATCH_NAMES.get(entity, _BATCH_NAMES["character"])

    def make_req(i: int) -> GenerationRequest:
        role = req.roles[i] if i < len(req.roles) and req.roles[i].strip() else \
            roles_pool[i % len(roles_pool)]
        if i < len(req.names) and req.names[i].strip():
            name = req.names[i]
        elif not settings.gpt_enabled:
            # 데모: 고유 이름 배정 (풀 초과 시 로마자 접미사)
            base = name_pool[i % len(name_pool)]
            name = base if i < len(name_pool) else f"{base} {i // len(name_pool) + 1}"
        else:
            name = ""  # 실제 GPT 가 고유하게 작명
        return GenerationRequest(
            entity_type=entity, name=name, genre=req.genre, role=role,
            art_style=req.art_style, keywords=req.keywords, assets=list(req.assets),
            image_scale=req.image_scale, variant_count=req.variant_count,
        )

    # 각 개체를 병렬 생성 (Pillow 인코딩은 GIL 을 해제하므로 스레드로 가속)
    def worker(i: int) -> GenerationResult:
        return run_pipeline(make_req(i), settings, f"{batch_id}/e{i}")

    with ThreadPoolExecutor(max_workers=min(4, count)) as pool:
        entries = list(pool.map(worker, range(count)))

    warnings: list[str] = []
    if entries and entries[0].warnings:
        # 개체마다 같은 경고가 반복되므로 대표로 한 번만 노출
        warnings = entries[0].warnings

    codex_asset = None
    if req.make_codex:
        pairs = [(e.concept, _portrait_abs(e, settings)) for e in entries]
        codex_png = settings.output_path / batch_id / "codex.png"
        codex_composer.compose_codex(entity, pairs, codex_png)
        codex_asset = GeneratedAsset(
            kind="codex", category="composite",
            path=str(codex_png.relative_to(settings.output_path)),
            label=f"{cat.ENTITY_TYPES.get(entity, '')} 도감",
            demo=not settings.gemini_enabled, is_image=True,
        )

    return BatchResult(batch_id=batch_id, entity_type=entity,
                       entries=entries, codex=codex_asset, warnings=warnings)


def _portrait_abs(entry: GenerationResult, settings: Settings) -> Path | None:
    """도감 카드에 쓸 대표 이미지의 절대 경로."""
    def pick():
        for a in entry.assets:
            if a.is_image and a.category == "character":
                return a
        for a in entry.assets:
            if a.is_image and a.kind not in ("video",):
                return a
        return None

    a = pick()
    return (settings.output_path / a.path) if a else None


def _pick_images(image_map: dict[str, Path]) -> dict[str, Path]:
    """시트/영상에서 쓸 대표 이미지(portrait/fullbody/icon)를 유연하게 선별."""
    def first(*keys):
        for k in keys:
            if k in image_map:
                return image_map[k]
        return None

    picks: dict[str, Path] = {}
    p = first("portrait", "expressions", "poses", "turnaround", "card_frame", "fullbody")
    fb = first("fullbody", "poses", "turnaround", "banner", "background", "portrait")
    ic = first("emblem", "weapon_icons", "skill_icons", "item_grid", "logo", "portrait")
    if p:
        picks["portrait"] = p
    if fb:
        picks["fullbody"] = fb
    if ic:
        picks["icon"] = ic
    # 최소 하나라도 있으면 나머지를 채움
    if picks:
        any_img = next(iter(picks.values()))
        picks.setdefault("portrait", any_img)
        picks.setdefault("fullbody", any_img)
        picks.setdefault("icon", any_img)
    return picks
