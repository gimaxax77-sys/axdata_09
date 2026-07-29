# 지면 오브젝트(팔다리 없는 침식체) 절차적 모션 합성 — 대기·일반공격·스킬·죽음
"""AI 기준 1장(base)에서 프레임을 절차적으로 합성한다(프레임 떨림 0).

각 모션은 base 를 스쿼시/런지/흔들림/스케일로 변형하고, 보라 균열을 발광
펄스시키며, 공격·스킬·죽음엔 파편(particles)을 얹는다. 대기는 루프, 나머지는
1회 재생(one-shot). breathe(스케일 호흡)의 확장판이며 캐릭터용 breathe 는 건드리지 않는다.
"""
from __future__ import annotations
from pathlib import Path
import math, random
import numpy as np
from PIL import Image, ImageDraw

MOTION_KINDS = {"idle", "attack", "skill", "death"}
# 프레임 수는 여기 두지 않는다 — asset_catalog 의 anim_*_ground variant_pool 길이가 단일 진실.
# synth 는 phase(0~1)만 받으므로 프레임 개수가 몇이든 동작한다.


def _purple_mask(arr: np.ndarray) -> np.ndarray:
    """보라 균열(에너지) 픽셀 마스크."""
    R, G, B, A = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    return (A > 30) & (B > 70) & (R > 60) & (G < R - 15) & (G < B - 10)


def _glowed(arr: np.ndarray, mask: np.ndarray, amt: float) -> np.ndarray:
    """보라 균열 밝기(R·B) 상승 → 발광."""
    if amt <= 0:
        return arr
    out = arr.astype(np.float32)
    for c in (0, 2):  # R, B
        ch = out[..., c]
        ch[mask] = np.clip(ch[mask] * (1.0 + amt), 0, 255)
    return out.astype(np.uint8)


def _place(img: Image.Image, scale: float, dx: int, dy: int, size: int = 512) -> Image.Image:
    """중심 기준 스케일 + 평행이동해 투명 캔버스에 배치."""
    w = max(8, int(round(size * scale)))
    s = img.resize((w, w), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    off = (size - w) // 2
    canvas.paste(s, (off + dx, off + dy), s)
    return canvas


def _fade_alpha(img: Image.Image, mul: float) -> Image.Image:
    if mul >= 1.0:
        return img
    r, g, b, a = img.split()
    a = a.point(lambda x: int(x * max(0.0, mul)))
    return Image.merge("RGBA", (r, g, b, a))


def _particles(img: Image.Image, specs) -> Image.Image:
    """파편 원 그리기. specs=[(x,y,rad,(r,g,b,a))]."""
    if not specs:
        return img
    d = ImageDraw.Draw(img)
    for x, y, rad, col in specs:
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=col)
    return img


def _shards(kind: str, phase: float, cx: int = 256, cy: int = 250):
    """모션별 파편 위치·색 계산(고정 시드로 일관)."""
    rnd = random.Random(hash(kind) & 0xffff)
    out = []
    ash = (150, 148, 160)
    void = (168, 120, 240)
    if kind == "attack" and 0.3 < phase < 0.75:
        t = (phase - 0.3) / 0.45
        for _ in range(6):
            ang = rnd.uniform(-0.5, 0.5)               # 앞(오른쪽) 방향
            dist = 40 + 140 * t
            x = cx + math.cos(ang) * dist
            y = cy + math.sin(ang) * dist - 10
            r = max(2, int(7 * (1 - t)))
            col = void if rnd.random() < 0.4 else ash
            out.append((x, y, r, col + (int(220 * (1 - t)),)))
    elif kind == "skill" and 0.45 < phase < 0.95:
        t = (phase - 0.45) / 0.5
        for k in range(10):
            ang = 2 * math.pi * k / 10 + rnd.uniform(-0.2, 0.2)  # 방사형
            dist = 30 + 170 * t
            x = cx + math.cos(ang) * dist
            y = cy + math.sin(ang) * dist
            r = max(2, int(9 * (1 - t)))
            col = void if k % 2 == 0 else ash
            out.append((x, y, r, col + (int(230 * (1 - t)),)))
    elif kind == "death" and phase > 0.3:
        t = (phase - 0.3) / 0.7
        for _ in range(9):
            x = cx + rnd.uniform(-120, 120)
            y = cy + rnd.uniform(-90, 40) + 160 * t        # 아래로 낙하
            r = max(2, int(8 * (1 - t)))
            out.append((x, y, r, ash + (int(200 * (1 - t)),)))
    return out


def _params(kind: str, p: float):
    """(scale, dx, dy, glow, alpha) 를 모션·위상별로."""
    if kind == "idle":
        return (1 + 0.015 * math.sin(2 * math.pi * p),
                0, int(round(3.5 * math.sin(2 * math.pi * p))),
                0.30 * (0.5 + 0.5 * math.sin(2 * math.pi * p)), 1.0)
    if kind == "attack":
        if p < 0.35:                       # 윈드업(스쿼시·뒤로)
            t = p / 0.35
            return (1 - 0.08 * t, int(-8 * t), int(6 * t), 0.2 + 0.3 * t, 1.0)
        if p < 0.55:                       # 스트라이크(앞으로 런지·발광 플래시)
            t = (p - 0.35) / 0.2
            return (1 + 0.10 * t, int(-8 + 24 * t), int(6 - 12 * t), 0.7, 1.0)
        t = (p - 0.55) / 0.45              # 회복
        return (1.10 - 0.10 * t, int(16 - 16 * t), int(-6 + 6 * t), 0.6 * (1 - t), 1.0)
    if kind == "skill":
        if p < 0.5:                        # 차징(흔들림·발광 상승)
            t = p / 0.5
            return (1 + 0.05 * t, int(round(2 * math.sin(20 * math.pi * p))), 0,
                    0.3 + 0.5 * t, 1.0)
        if p < 0.7:                        # 버스트(팽창·최대 발광)
            t = (p - 0.5) / 0.2
            return (1.05 + 0.12 * t, 0, int(-4 * t), 0.9, 1.0)
        t = (p - 0.7) / 0.3                # 세틀
        return (1.17 - 0.17 * t, 0, int(-4 + 4 * t), 0.9 * (1 - t), 1.0)
    if kind == "death":
        if p < 0.25:                       # 셔더
            t = p / 0.25
            return (1.0, int(round(3 * math.sin(30 * math.pi * p))), 0,
                    0.4 * (1 - t), 1.0)
        t = (p - 0.25) / 0.75              # 붕괴(가라앉음·페이드·발광 소멸)
        return (1 - 0.12 * t, 0, int(10 * t), 0.4 * (1 - t), 1.0 - t)
    return (1.0, 0, 0, 0.0, 1.0)


def synth(kind: str, base_path: Path, out_path: Path, phase: float) -> None:
    """base 에서 kind·phase 프레임 1장을 합성해 out_path 에 저장."""
    base = Image.open(base_path).convert("RGBA")
    arr = np.array(base)
    mask = _purple_mask(arr)
    scale, dx, dy, glow, alpha = _params(kind, phase)
    glowed = Image.fromarray(_glowed(arr, mask, glow), "RGBA")
    frame = _place(glowed, scale, dx, dy, size=base.width)
    frame = _fade_alpha(frame, alpha)
    frame = _particles(frame, _shards(kind, phase))
    frame.save(out_path)
