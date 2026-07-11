"""파이프라인 오케스트레이션.

요청 → GPT 기획 → (선택 에셋별) Gemini 아트 → 시트 조합 → CapCut/영상
순으로 실행하고, 생성된 산출물 목록을 반환한다.
"""
from __future__ import annotations

from pathlib import Path

import random
from concurrent.futures import ThreadPoolExecutor

from ..config import Settings
from ..logging_config import get_logger
from ..models import (
    BatchRequest,
    BatchResult,
    EntityConcept,
    GeneratedAsset,
    GenerationRequest,
    GenerationResult,
    RegenerateRequest,
)
from . import asset_catalog as cat
from . import (
    capcut_service,
    codex_composer,
    gemini_service,
    gpt_service,
    progress,
    sheet_composer,
    spritesheet,
)

log = get_logger(__name__)


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

    # 진행률: 기획(1) + 이미지 에셋(N) + 시트(0/1) + 영상(0/1)
    pid = req.progress_id
    image_keys = [k for k in selected if cat.CATALOG[k].is_image]
    total_steps = 1 + len(image_keys) + (1 if "sheet" in selected else 0) \
        + (1 if "video" in selected else 0)
    progress.start(pid, total_steps, "기획 생성 중…")

    # 1) GPT — 기획서
    progress.check(pid)
    concept = gpt_service.generate_concept(req, settings)
    progress.advance(pid, "기획 완료")
    if not settings.gpt_enabled:
        warnings.append("OPENAI_API_KEY 미설정 — 기획은 데모 생성기로 만들어졌습니다.")
    (job_dir / "concept.json").write_text(
        concept.model_dump_json(indent=2), encoding="utf-8"
    )

    # 2) 이미지 에셋 생성 (선택된 것만)
    #    캐릭터 일관성: 첫 캐릭터 에셋(초상화 우선)을 앵커로 삼아 나머지
    #    캐릭터 에셋에 레퍼런스로 전달한다.
    image_specs = [cat.CATALOG[k] for k in selected if cat.CATALOG[k].is_image]
    if req.consistency:
        image_specs.sort(key=lambda s: (not s.character_ref, s.key != "portrait"))

    image_map: dict[str, Path] = {}  # 시트/영상에서 재사용할 대표 이미지
    demo_art = False
    anchor = None  # PIL.Image — 캐릭터/스타일 앵커 레퍼런스
    for idx, spec in enumerate(image_specs):
        progress.check(pid)
        progress.step(pid, 1 + idx, f"{spec.label} 생성 중…")
        # 레퍼런스 결정: 캐릭터 에셋=정체성, 그 외+스타일락=스타일-only
        use_ref = None
        style_only = False
        if anchor is not None:
            if req.consistency and spec.character_ref:
                use_ref = anchor
            elif req.style_lock and not spec.character_ref:
                use_ref, style_only = anchor, True

        results = gemini_service.generate_asset(
            spec, concept, job_dir, settings,
            scale=req.image_scale, variant_count=req.variant_count,
            reference=use_ref, style_only=style_only,
            transparent=req.transparent, model=req.image_model,
        )
        for res in results:
            image_map.setdefault(spec.key, res.path)  # 첫 변형을 대표로
            if res.demo:
                demo_art = True
            assets.append(GeneratedAsset(
                kind=spec.key, category=spec.category, path=rel(res.path),
                label=res.label, demo=res.demo, is_image=True,
            ))

        # 애니메이션: 가로 스트립 시트 + 반복 GIF 자동 생성
        if spec.is_anim and len(results) > 1:
            sheet_png = job_dir / f"{spec.key}_sheet.png"
            atlas_json = job_dir / f"{spec.key}_atlas.json"
            spritesheet.pack([(r.variant or spec.label, r.path) for r in results],
                             sheet_png, atlas_json, single_row=True)
            assets.append(GeneratedAsset(
                kind=f"{spec.key}_sheet", category="composite", path=rel(sheet_png),
                label=f"{spec.label} 스트립", demo=demo_art, is_image=True))
            gif = job_dir / f"{spec.key}.gif"
            if spritesheet.make_gif([r.path for r in results], gif, fps=8):
                assets.append(GeneratedAsset(
                    kind=f"{spec.key}_gif", category="composite", path=rel(gif),
                    label=f"{spec.label} 미리보기(GIF)", demo=demo_art, is_image=True))
        # 스프라이트 시트: 그 외 다변형 에셋을 아틀라스로 패킹(옵션)
        elif req.sprite_sheet and len(results) > 1:
            sheet_png = job_dir / f"{spec.key}_sheet.png"
            atlas_json = job_dir / f"{spec.key}_atlas.json"
            packed = spritesheet.pack(
                [(r.variant or spec.label, r.path) for r in results],
                sheet_png, atlas_json,
            )
            if packed:
                assets.append(GeneratedAsset(
                    kind=f"{spec.key}_sheet", category="composite",
                    path=rel(sheet_png), label=f"{spec.label} 스프라이트 시트",
                    demo=demo_art, is_image=True,
                ))

        # 타일셋: 이음새 완화 + 3x3 타일 미리보기
        if spec.key == "tileset" and results:
            tile_path = results[0].path
            gemini_service.apply_tileable(tile_path)
            preview = job_dir / "tileset_preview.png"
            if gemini_service.tile_preview_file(tile_path, preview, 3):
                assets.append(GeneratedAsset(
                    kind="tileset_preview", category="composite", path=rel(preview),
                    label="타일 3x3 미리보기", demo=demo_art, is_image=True))

        # 앵커 확보: 실제로 생성된(데모 아님) 첫 캐릭터 에셋의 첫 변형
        if (anchor is None and spec.character_ref
                and results and not results[0].demo):
            try:
                from PIL import Image
                anchor = Image.open(results[0].path).convert("RGB")
            except Exception:
                anchor = None
    if demo_art and not settings.gemini_enabled:
        warnings.append("GEMINI_API_KEY 미설정 — 아트는 데모 플레이스홀더로 생성되었습니다.")
    if req.transparent:
        warnings.append("투명 배경 ON — 컷아웃 에셋은 배경을 제거해 알파 PNG 로 저장됩니다 "
                        "(rembg 설치 시 정밀, 미설치 시 단순 제거).")

    # 시트/영상에 쓸 대표 이미지 3종 선별
    picks = _pick_images(image_map)

    # 3) 캐릭터 시트 (PNG + PDF)
    if "sheet" in selected:
        progress.check(pid)
        progress.advance(pid, "캐릭터 시트 조합 중…")
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
        progress.check(pid)
        progress.advance(pid, "쇼케이스 영상 만드는 중…")
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

    result = GenerationResult(job_id=job_id, concept=concept, assets=assets, warnings=warnings)
    # 히스토리용 결과 저장
    try:
        (job_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    except Exception as exc:
        log.debug("result.json 저장 실패(무시): %s", exc)
    progress.finish(pid)
    return result


def regenerate_asset(req: RegenerateRequest, settings: Settings,
                     job_id: str) -> list[GeneratedAsset]:
    """기존 잡 폴더의 이미지 에셋 하나를 다시 생성하고 result.json 을 갱신한다.

    concept.json 을 앵커로 재사용한다. 애니메이션/타일셋 후처리는 해당
    스펙이면 함께 재실행한다. (시트/영상 등 통합 산출물은 대상 아님.)
    """
    import json

    job_dir = settings.output_path / job_id
    if not job_dir.is_dir():
        raise FileNotFoundError("잡 폴더를 찾을 수 없습니다.")

    key = req.asset_key
    spec = cat.CATALOG.get(key)
    if spec is None or not spec.is_image:
        raise ValueError("이미지 에셋만 다시 생성할 수 있습니다.")

    concept_path = job_dir / "concept.json"
    if not concept_path.exists():
        raise FileNotFoundError("concept.json 이 없어 다시 생성할 수 없습니다.")
    concept = EntityConcept(**json.loads(concept_path.read_text(encoding="utf-8")))

    def rel(p: Path) -> str:
        return str(p.relative_to(settings.output_path))

    # 이전 산출물(변형 포함) 제거 후 재생성
    for old in job_dir.glob(f"{key}*.png"):
        try:
            old.unlink()
        except OSError:
            pass

    results = gemini_service.generate_asset(
        spec, concept, job_dir, settings,
        scale=req.image_scale, variant_count=req.variant_count,
        reference=None, style_only=False,
        transparent=req.transparent, model=req.image_model,
    )
    new_assets: list[GeneratedAsset] = []
    demo_art = any(r.demo for r in results)
    for res in results:
        new_assets.append(GeneratedAsset(
            kind=spec.key, category=spec.category, path=rel(res.path),
            label=res.label, demo=res.demo, is_image=True))

    # 애니메이션/타일셋 부가 산출물 재생성
    if spec.is_anim and len(results) > 1:
        sheet_png = job_dir / f"{spec.key}_sheet.png"
        atlas_json = job_dir / f"{spec.key}_atlas.json"
        spritesheet.pack([(r.variant or spec.label, r.path) for r in results],
                         sheet_png, atlas_json, single_row=True)
        new_assets.append(GeneratedAsset(
            kind=f"{spec.key}_sheet", category="composite", path=rel(sheet_png),
            label=f"{spec.label} 스트립", demo=demo_art, is_image=True))
        gif = job_dir / f"{spec.key}.gif"
        if spritesheet.make_gif([r.path for r in results], gif, fps=8):
            new_assets.append(GeneratedAsset(
                kind=f"{spec.key}_gif", category="composite", path=rel(gif),
                label=f"{spec.label} 미리보기(GIF)", demo=demo_art, is_image=True))
    if spec.key == "tileset" and results:
        gemini_service.apply_tileable(results[0].path)
        preview = job_dir / "tileset_preview.png"
        if gemini_service.tile_preview_file(results[0].path, preview, 3):
            new_assets.append(GeneratedAsset(
                kind="tileset_preview", category="composite", path=rel(preview),
                label="타일 3x3 미리보기", demo=demo_art, is_image=True))

    # result.json 갱신: 같은 kind 계열(스펙 키로 시작) 항목 교체
    rj = job_dir / "result.json"
    prefixes = {spec.key, f"{spec.key}_sheet", f"{spec.key}_gif"}
    if spec.key == "tileset":
        prefixes.add("tileset_preview")
    if rj.exists():
        try:
            data = json.loads(rj.read_text(encoding="utf-8"))
            kept = [a for a in data.get("assets", []) if a.get("kind") not in prefixes]
            data["assets"] = kept + [a.model_dump() for a in new_assets]
            rj.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            log.debug("regenerate result.json 갱신 실패(무시): %s", exc)
    return new_assets


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
            consistency=req.consistency, transparent=req.transparent,
            sprite_sheet=req.sprite_sheet, style_lock=req.style_lock,
            image_model=req.image_model,
        )

    # 진행률: 개체 N + 도감(0/1). 개체 하위 파이프라인은 progress_id 를
    # 비워 두어(make_req 기본값) 배치 진행률과 충돌하지 않게 한다.
    pid = req.progress_id
    total_steps = count + (1 if req.make_codex else 0)
    progress.start(pid, total_steps, "개체 생성 중…")

    # 각 개체를 병렬 생성 (Pillow 인코딩은 GIL 을 해제하므로 스레드로 가속)
    def worker(i: int) -> GenerationResult:
        progress.check(pid)
        res = run_pipeline(make_req(i), settings, f"{batch_id}/e{i}")
        progress.advance(pid, f"{i + 1}/{count} 개체 완료")
        return res

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

    result = BatchResult(batch_id=batch_id, entity_type=entity,
                         entries=entries, codex=codex_asset, warnings=warnings)
    # 히스토리용 결과 저장
    try:
        (settings.output_path / batch_id / "result.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8")
    except Exception as exc:
        log.debug("batch result.json 저장 실패(무시): %s", exc)
    progress.finish(pid)
    return result


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
