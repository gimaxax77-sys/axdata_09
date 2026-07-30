# PixelLab 레퍼런스용 고화질 캐릭터 아트 생성 — 정측면·깔끔한 실루엣(애니 일관성용)
"""PixelLab의 '레퍼런스 이미지' 모드에 넣을 원본 아트를 만든다.
레퍼런스는 사이드뷰·전신·단순 배경이어야 PixelLab이 프레임 일관성을 잘 유지한다.

사용법:
    python scripts/ref_for_pixellab.py            # 기사(knight)
    python scripts/ref_for_pixellab.py mage       # 다른 프리셋
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.models import EntityConcept
from app.services import asset_catalog as cat
from app.services.gemini_service import generate_asset

# 엘 로그 톤: 무광 강철 다크 + 골드
PRESETS = {
    "knight": dict(
        name="기사", name_en="Knight", role="근접 탱커",
        visual="fantasy knight in matte dark steel plate armor with gold trim, sword and kite shield",
    ),
    "mage": dict(
        name="마법사", name_en="Mage", role="마법 딜러",
        visual="fantasy mage in dark robe with gold embroidery, staff with glowing crystal",
    ),
}

# 레퍼런스 품질을 좌우하는 핵심 지시 — 전신·단순 배경·또렷한 실루엣.
#   angle 인자로 시점 선택: side(정측면) / three_quarter(3/4 측면, 얼굴 더 보임)
ANGLES = {
    "side": "full body side view facing right, strict side profile",
    "front": (
        "full body front view facing the viewer, symmetrical standing pose, "
        "head and torso squarely toward camera, "
        "eye-level camera (not top-down)"
    ),
    "three_quarter": (
        "full body three-quarter side view facing right, body turned slightly toward viewer, "
        "face and chest partially visible, still a side-scrolling camera (not top-down)"
    ),
}
REF_TAIL = (
    "clean readable silhouette, simple flat plain background, "
    "game character reference sheet, stylized, matte finish, no motion blur"
)

# front 각도 전용 지시(프롬프트 맨 끝에 붙는다).
#   배경: 회색은 갑옷과 색이 겹쳐 키잉이 안 되고 다리 사이 같은 막힌 구역도
#         안 빠진다 → 캐릭터에 없는 마젠타로 고정해 색으로 도려낸다.
#   포즈: 무기를 땅에 짚으면 스프라이트 변환 시 실루엣이 무너진다 → 세워 든다.
#   ⚠ 짧게 유지할 것 — 길면 gemini_service 의 글자 금지·화풍 고정 지시를
#     뒤로 밀어내 화풍이 튀고 이미지에 글자가 박힌다(실제로 겪음).
FRONT_RULES = (
    "Background is one flat solid magenta #FF00FF, including the gaps between the "
    "legs and arms; no shadow, no ground. The sword is held upright, blade pointing "
    "up in front of the chest, never touching the ground. No text anywhere."
)


def main() -> int:
    key = sys.argv[1] if len(sys.argv) > 1 else "knight"
    angle = sys.argv[2] if len(sys.argv) > 2 else "side"
    p = PRESETS.get(key, PRESETS["knight"])
    ref_style = f"{ANGLES.get(angle, ANGLES['side'])}, {REF_TAIL}"
    settings = get_settings()
    spec = cat.CATALOG["fullbody"]  # 768x1024 전신

    concept = EntityConcept(
        entity_type="character", name=p["name"], name_en=p["name_en"],
        genre="fantasy", role=p["role"],
        appearance=p["visual"], visual_core=p["visual"],
        color_palette=["#15171c", "#4a515f", "#ffd257", "#9aa0b5"],
        art_style=ref_style,
    )

    out_dir = Path(__file__).resolve().parent.parent / "outputs" / f"pixellab_ref_{key}_{angle}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[생성] {p['name']}({key}) · fullbody 768x1024 · PixelLab 레퍼런스용 {angle}")
    results = generate_asset(
        spec, concept, out_dir, settings, variant_count=1,
        extra_prompt=FRONT_RULES if angle == "front" else "",
    )
    for r in results:
        print(f"  → {getattr(r, 'path', r)}")
    print(f"[완료] {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
