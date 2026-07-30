# 코어 커맨더 침식체 '잿가루 무리' idle 시범 — 09 스튜디오 anim_idle_ground 프리셋 실생성
"""클린 base(idle_01)를 레퍼런스로 3/4 탑다운 지면 오브젝트 대기 프레임 생성.
anim_idle_ground: 기준 1장만 AI 생성 + 나머지는 breathe 합성 → 시트+GIF+투명.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from app.config import get_settings
from app.models import EntityConcept
from app.services import asset_catalog as cat, spritesheet
from app.services.gemini_service import generate_asset

REF = Path(r"D:/.CODE/AXdata/Art pack_assets/코어 커맨드_아트셋/침식체/idle_sprite_6_individual_transparent_png/idle_01.png")

def main() -> int:
    if not REF.exists():
        print("레퍼런스 없음:", REF); return 1
    settings = get_settings()
    spec = cat.CATALOG["anim_idle_ground"]
    reference = Image.open(REF).convert("RGBA")

    concept = EntityConcept(
        entity_type="monster", name="잿가루 무리", name_en="Ashling",
        genre="dark sci-fi", role="침식체",
        appearance="ashen grey-white rounded rock cluster with glowing void-purple cracks",
        visual_core=("a low cluster of ashen grey-white rounded rock shards packed together, "
                     "glowing void-purple energy cracks between the stones, wispy grey ash at "
                     "the base, desaturated colorless, entropic corrupted blight look"),
        color_palette=["#8a8698", "#d8d5dc", "#7c4fd0", "#3a3540"],
        art_style="corrupted blight creature, ashen desaturated, glowing void-purple cracks, ominous, clean cel-shaded game sprite",
    )
    out_dir = Path(__file__).resolve().parent.parent / "outputs" / "blight_ashling_idle"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[생성] 잿가루 무리 · anim_idle_ground · 6프레임 · 레퍼런스={REF.name} · 투명")
    results = generate_asset(
        spec, concept, out_dir, settings,
        variant_count=6, reference=reference, style_only=False, transparent=True,
    )
    real = sum(0 if r.demo else 1 for r in results)
    print(f"  생성 {len(results)}장 (실제 {real} / 데모 {len(results)-real})")
    for r in results:
        print("   →", Path(r.path).name, "(demo)" if r.demo else "")

    # 시트 + GIF
    sheet_png = out_dir / "ashling_idle_sheet.png"
    atlas = out_dir / "ashling_idle_atlas.json"
    spritesheet.pack([(r.variant or "idle", Path(r.path)) for r in results], sheet_png, atlas, single_row=True)
    gif = out_dir / "ashling_idle.gif"
    spritesheet.make_gif([Path(r.path) for r in results], gif, fps=8)
    print("  시트:", sheet_png.name, "| GIF:", gif.name)
    print("[완료]", out_dir)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
