"""파이프라인 오케스트레이션.

요청 → GPT 기획 → Gemini 아트 → 시트 조합 → CapCut/영상 순으로 실행하고,
생성된 산출물 목록을 반환한다.
"""
from __future__ import annotations

from pathlib import Path

from ..config import Settings
from ..models import (
    CharacterRequest,
    GeneratedAsset,
    GenerationResult,
)
from . import capcut_service, gemini_service, gpt_service, sheet_composer


def _slug(name: str) -> str:
    keep = [c if c.isalnum() else "-" for c in name.strip().lower()]
    s = "".join(keep).strip("-") or "character"
    return s[:40]


def run_pipeline(
    req: CharacterRequest,
    settings: Settings,
    job_id: str,
) -> GenerationResult:
    job_dir = settings.output_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    assets: list[GeneratedAsset] = []

    # 1) GPT — 캐릭터 기획서
    concept = gpt_service.generate_concept(req, settings)
    if not settings.gpt_enabled:
        warnings.append("OPENAI_API_KEY 미설정 — 캐릭터 기획은 데모 생성기로 만들어졌습니다.")
    (job_dir / "concept.json").write_text(
        concept.model_dump_json(indent=2), encoding="utf-8"
    )

    def rel(p: Path) -> str:
        return str(p.relative_to(settings.output_path))

    # 2) Gemini — 아트 3종
    images: dict[str, Path] = {}
    demo_art = False
    if req.make_assets or req.make_sheet or req.make_video:
        results = gemini_service.generate_character_images(concept, job_dir, settings)
        labels = {"portrait": "초상화", "fullbody": "전신 스프라이트", "icon": "엠블럼 아이콘"}
        for kind, (path, is_real) in results.items():
            images[kind] = path
            if not is_real:
                demo_art = True
            if req.make_assets:
                assets.append(GeneratedAsset(
                    kind=kind, path=rel(path), label=labels[kind], demo=not is_real,
                ))
        if demo_art and not settings.gemini_enabled:
            warnings.append("GEMINI_API_KEY 미설정 — 아트는 데모 플레이스홀더로 생성되었습니다.")

    # 3) 캐릭터 시트 (PNG + PDF)
    if req.make_sheet:
        png = job_dir / "character_sheet.png"
        pdf = job_dir / "character_sheet.pdf"
        sheet_composer.compose_sheet(concept, images, png, pdf)
        assets.append(GeneratedAsset(kind="sheet_png", path=rel(png),
                                     label="캐릭터 시트 (PNG)", demo=demo_art))
        assets.append(GeneratedAsset(kind="sheet_pdf", path=rel(pdf),
                                     label="캐릭터 시트 (PDF)", demo=demo_art))

    # 4) CapCut draft + 미리보기 영상
    if req.make_video and images:
        storyboard = capcut_service.build_storyboard(concept, images)

        draft_dir = job_dir / "capcut_draft"
        _, native = capcut_service.build_capcut_draft(concept, images, draft_dir, storyboard)
        assets.append(GeneratedAsset(
            kind="capcut_draft", path=rel(draft_dir),
            label="CapCut 프로젝트" + ("" if native else " (스토리보드)"),
            demo=not native,
        ))
        if not native:
            warnings.append(
                "CapCut 네이티브 draft 는 pyJianYingDraft 설치 시 생성됩니다 — "
                "현재는 스토리보드 JSON + 에셋 + 안내가 제공됩니다."
            )

        gif = job_dir / "showcase.gif"
        mp4 = job_dir / "showcase.mp4"
        _, mp4_out = capcut_service.build_preview_video(concept, images, storyboard, gif, mp4)
        assets.append(GeneratedAsset(kind="video", path=rel(gif),
                                     label="쇼케이스 미리보기 (GIF)", demo=demo_art))
        if mp4_out:
            assets.append(GeneratedAsset(kind="video", path=rel(mp4_out),
                                         label="쇼케이스 영상 (MP4)", demo=demo_art))

    return GenerationResult(
        job_id=job_id, concept=concept, assets=assets, warnings=warnings
    )
