"""파이프라인 오케스트레이션.

요청 → GPT 기획 → (선택 에셋별) Gemini 아트 → 시트 조합 → CapCut/영상
순으로 실행하고, 생성된 산출물 목록을 반환한다.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..models import GeneratedAsset, GenerationRequest, GenerationResult
from . import asset_catalog as cat
from . import capcut_service, gemini_service, gpt_service, sheet_composer


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
        for res in gemini_service.generate_asset(spec, concept, job_dir, settings):
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
