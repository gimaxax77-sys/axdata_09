# 잿가루 무리 4모션(대기·일반공격·스킬·죽음) — 단일 base에서 절차 합성 + 발광 펄스
"""동일 개체 일관성을 위해 base 1장(기존 AI 생성물)에서 4모션을 모두 합성.
각 모션: motion.synth(kind, base, out, phase). 시트+GIF 자동. 투명 유지.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services import asset_catalog as cat, motion, spritesheet

BASE = Path(__file__).resolve().parent.parent / "outputs" / "blight_ashling_idle" / "anim_idle_ground_1.png"
OUT = Path(__file__).resolve().parent.parent / "outputs" / "blight_ashling_4motion"
FPS = {"idle": 8, "attack": 14, "skill": 14, "death": 10}

def main() -> int:
    if not BASE.exists():
        print("base 없음:", BASE); return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for kind in ("idle", "attack", "skill", "death"):
        n = len(cat.CATALOG[f"anim_{kind}_ground"].variant_pool)  # 프레임 수 = 카탈로그
        paths = []
        for i in range(n):
            p = OUT / f"{kind}_{i:02d}.png"
            motion.synth(kind, BASE, p, phase=i / n)
            paths.append(p)
        sheet = OUT / f"ashling_{kind}_sheet.png"
        spritesheet.pack([(f"{kind}{i}", p) for i, p in enumerate(paths)], sheet,
                         OUT / f"ashling_{kind}_atlas.json", single_row=True)
        gif = OUT / f"ashling_{kind}.gif"
        spritesheet.make_gif(paths, gif, fps=FPS[kind])
        print(f"  {kind}: {n}프레임 → {sheet.name}, {gif.name}")
    print("[완료]", OUT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
