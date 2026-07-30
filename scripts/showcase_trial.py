# 엘로그 픽셀 영웅을 레퍼런스로 고화질 쇼케이스 1종 시범 생성(경로 B, img2img)
"""픽셀 초상(512x512)을 앵커로 동일 캐릭터를 고화질 fullbody 일러스트로 리드로우.

사용법:
    python scripts/showcase_trial.py            # 기사(knight) 경로 B(레퍼런스) 1장
    python scripts/showcase_trial.py knight noref  # 경로 A(텍스트만, 레퍼런스 없음)

레퍼런스는 axdata_11의 assets/char/fantasy_pixel/<id>.png 를 쓴다.
변형 1장만(variant_count=1) 생성해 비용 최소화. 결과·실비용을 출력한다.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image
from app.config import get_settings
from app.models import EntityConcept
from app.services import asset_catalog as cat
from app.services.gemini_service import generate_asset

GAME = Path(r"D:\.CODE\AXdata\axdata_11\axdata_11")

# 픽셀 원본을 보고 적은 최소 기획(경로 B라 외형은 레퍼런스가 주도, 텍스트는 스타일·품질 유도).
HEROES = {
    "knight": dict(
        name="기사", name_en="Knight", role="근접 탱커 / 뱅가드",
        appearance="full plate steel armor, kite shield and sword, blue tabard, heroic knight",
        palette=["#8891a8", "#5c6480", "#c9ccd8", "#3a7fc4"],
    ),
}


def main() -> int:
    hid = sys.argv[1] if len(sys.argv) > 1 else "knight"
    info = HEROES.get(hid, HEROES["knight"])
    ref_path = GAME / "assets" / "char" / "fantasy_pixel" / f"{hid}.png"
    if not ref_path.exists():
        print(f"레퍼런스 없음: {ref_path}")
        return 1

    noref = "noref" in sys.argv[2:]
    reference = None if noref else Image.open(ref_path).convert("RGBA")
    settings = get_settings()
    spec = cat.CATALOG["fullbody"]  # 전신 768x1024 — 쇼케이스용 큰 그림

    concept = EntityConcept(
        entity_type="character", name=info["name"], name_en=info["name_en"],
        genre="fantasy", role=info["role"],
        appearance=info["appearance"],
        visual_core=info["appearance"],
        color_palette=info["palette"],
        art_style="high-quality stylized fantasy game splash art, painterly, dramatic lighting, clean silhouette",
    )

    tag = "noref" if noref else "ref"
    out_dir = Path(__file__).resolve().parent.parent / "outputs" / f"showcase_trial_{hid}_{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    mode = "경로A 텍스트만(레퍼런스 없음)" if noref else f"경로B img2img(레퍼런스 {ref_path.name}, 동일 캐릭터)"
    print(f"[생성] {info['name']}({hid}) · fullbody 768x1024 · {mode}")
    results = generate_asset(
        spec, concept, out_dir, settings,
        variant_count=1, reference=reference, style_only=False,
    )
    for r in results:
        print(f"  → {getattr(r, 'path', r)}")
    print(f"[완료] 출력 폴더: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
