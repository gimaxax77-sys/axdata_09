"""데모 플레이스홀더 아트 — API 키/호출 실패 시 Pillow 로 카테고리별
플레이스홀더 이미지를 그린다. gemini_service 에서 분리(가독성).
"""
from __future__ import annotations

import hashlib
import math

from PIL import Image, ImageDraw

from .fonts import load_font


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (80, 80, 100)


# 속성명 → 대표색 (VFX 플레이스홀더용)
_ELEMENT_COLORS = {
    "화염": (255, 90, 30), "화염 히트": (255, 90, 30), "용암": (255, 70, 20),
    "빙결": (90, 200, 255), "빙결 히트": (90, 200, 255), "물": (60, 140, 255),
    "전격": (255, 230, 90), "감전": (255, 230, 90), "섬광": (255, 250, 210),
    "맹독": (150, 230, 70), "암흑": (150, 80, 220), "신성": (255, 240, 180),
    "대지": (200, 150, 90), "질풍": (140, 255, 200), "회오리": (140, 255, 200),
    "치유": (120, 255, 160), "보호막": (120, 200, 255), "버프": (255, 220, 120),
    "디버프": (200, 90, 200), "폭발": (255, 140, 40), "폭산": (255, 140, 40),
    "참격": (230, 240, 255), "베기": (230, 240, 255), "오라": (180, 130, 255),
}


def _vfx_color(label, palette) -> tuple[int, int, int]:
    # 라벨 끝의 변형명(예: "이름 · 화염")에서 속성 추출
    elem = label.split("·")[-1].strip() if "·" in label else ""
    if elem in _ELEMENT_COLORS:
        return _ELEMENT_COLORS[elem]
    for k, c in _ELEMENT_COLORS.items():
        if k in label:
            return c
    return _hex((palette or ["#7c5cff"])[0])


def generate_placeholder(out_path, size, label, palette, style) -> None:
    if style == "vfx":
        img = _placeholder_vfx(size, label, palette)
        draw = ImageDraw.Draw(img, "RGBA")
        _label_badge(img, draw, label)
        _demo_mark(draw, *size)
        img.save(out_path)
        return
    if style == "pixel":
        img = _placeholder_pixel(size, label, palette)
    else:
        w, h = size
        colors = [_hex(c) for c in (palette or ["#2E1A47", "#C89B3C", "#E6D5B8"])]
        img = _gradient(w, h, colors[0], colors[-1])
        draw = ImageDraw.Draw(img, "RGBA")
        _scatter_shapes(draw, w, h, colors, label)

        if style in ("figure", "card", "splash"):
            _silhouette(draw, w, h, colors[len(colors) // 2])
        if style == "card":
            _card_frame(draw, w, h, colors)
        if style == "logo":
            _logo_text(img, draw, label, colors)
        elif style in ("scene", "splash"):
            _horizon(draw, w, h, colors)
        if style == "splash":
            _vignette(img, colors)
        if style == "namecard":
            _namecard_frame(draw, w, h, colors)
        if style == "button":
            _button_shape(draw, w, h, colors)
        if style == "panel":
            _panel_frame(draw, w, h, colors)
        if style == "hud":
            _hud_bars(draw, w, h, colors)

    draw = ImageDraw.Draw(img, "RGBA")
    if style != "logo":
        _label_badge(img, draw, label)
    _demo_mark(draw, *size)
    img.save(out_path)


def _gradient(w, h, c1, c2) -> Image.Image:
    img = Image.new("RGB", (w, h))
    for y in range(h):
        t = y / max(1, h - 1)
        row = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        img.paste(Image.new("RGB", (w, 1), row), (0, y))
    return img


def _scatter_shapes(draw, w, h, colors, seed_label) -> None:
    rnd = _LCG(int(hashlib.md5(seed_label.encode()).hexdigest(), 16))
    for _ in range(14):
        cx, cy = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.randint(int(min(w, h) * 0.05), int(min(w, h) * 0.26))
        col = colors[rnd.randint(0, len(colors) - 1)]
        alpha = rnd.randint(35, 120)
        box = [cx - r, cy - r, cx + r, cy + r]
        s = rnd.randint(0, 2)
        if s == 0:
            draw.ellipse(box, fill=(*col, alpha))
        elif s == 1:
            draw.rectangle(box, fill=(*col, alpha))
        else:
            draw.polygon(_poly(cx, cy, r, rnd.randint(3, 6), rnd.random() * 3.14),
                         fill=(*col, alpha))


def _silhouette(draw, w, h, color) -> None:
    cx = w // 2
    hr = int(min(w, h) * 0.10)
    hy = int(h * 0.34)
    draw.ellipse([cx - hr, hy - hr, cx + hr, hy + hr], fill=(*color, 75))
    draw.polygon([
        (cx - int(w * 0.17), h), (cx - int(w * 0.09), hy + hr),
        (cx + int(w * 0.09), hy + hr), (cx + int(w * 0.17), h),
    ], fill=(*color, 75))


def _horizon(draw, w, h, colors) -> None:
    # 원경 산 실루엣 (배경/배너용)
    base = int(h * 0.72)
    col = colors[0]
    pts = [(0, base)]
    rnd = _LCG(base + w)
    x = 0
    while x <= w:
        pts.append((x, base - rnd.randint(0, int(h * 0.18))))
        x += max(40, w // 12)
    pts += [(w, base), (w, h), (0, h)]
    draw.polygon(pts, fill=(*col, 150))


def _card_frame(draw, w, h, colors) -> None:
    accent = colors[2 if len(colors) > 2 else 0]
    m = int(min(w, h) * 0.04)
    draw.rounded_rectangle([m, m, w - m, h - m], radius=m, outline=(*accent, 230),
                           width=max(4, m // 3))
    # 상단 이름 배너 / 하단 스탯 박스
    draw.rounded_rectangle([m * 2, m * 2, w - m * 2, int(h * 0.14)], radius=m // 2,
                           fill=(0, 0, 0, 150), outline=(*accent, 200), width=3)
    draw.rounded_rectangle([m * 2, int(h * 0.86), w - m * 2, h - m * 2], radius=m // 2,
                           fill=(0, 0, 0, 150), outline=(*accent, 200), width=3)


def _vignette(img, colors) -> None:
    """가장자리를 어둡게 (스플래시 아트 시네마틱 느낌)."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([-w * 0.2, -h * 0.2, w * 1.2, h * 1.2], fill=255)
    mask = mask.point(lambda v: int(v * 0.85))
    dark = Image.new("RGB", (w, h), (8, 6, 14))
    img.paste(Image.composite(img, dark, mask), (0, 0))


def _namecard_frame(draw, w, h, colors) -> None:
    """가로형 프로필 카드: 아바타 원 + 이름 바 + 테두리."""
    accent = colors[2 if len(colors) > 2 else 0]
    m = int(h * 0.06)
    draw.rounded_rectangle([m, m, w - m, h - m], radius=m, outline=(*accent, 230),
                           width=max(4, m // 4))
    # 좌측 아바타 원
    av = int(h * 0.62)
    ax, ay = int(w * 0.06), (h - av) // 2
    draw.ellipse([ax, ay, ax + av, ay + av], fill=(0, 0, 0, 120),
                 outline=(*accent, 230), width=4)
    # 우측 이름/설명 바
    tx = ax + av + int(w * 0.04)
    draw.rounded_rectangle([tx, int(h * 0.30), w - m * 2, int(h * 0.44)],
                           radius=8, fill=(*accent, 210))
    draw.rounded_rectangle([tx, int(h * 0.50), int(w * 0.82), int(h * 0.60)],
                           radius=6, fill=(0, 0, 0, 130))
    draw.rounded_rectangle([tx, int(h * 0.63), int(w * 0.70), int(h * 0.71)],
                           radius=6, fill=(0, 0, 0, 130))


def _button_shape(draw, w, h, colors) -> None:
    """알약형 버튼 실루엣 (인게임 버튼 UI)."""
    accent = colors[2 if len(colors) > 2 else 0]
    top = colors[1 if len(colors) > 1 else 0]
    m = int(min(w, h) * 0.16)
    r = (h - 2 * m) // 2
    draw.rounded_rectangle([m, m, w - m, h - m], radius=r, fill=(*accent, 220),
                           outline=(255, 255, 255, 60), width=3)
    # 상단 하이라이트
    draw.rounded_rectangle([m + 6, m + 6, w - m - 6, m + (h - 2 * m) // 2],
                           radius=r, fill=(*top, 90))


def _panel_frame(draw, w, h, colors) -> None:
    """창/패널 프레임 (인벤토리·대화창)."""
    accent = colors[2 if len(colors) > 2 else 0]
    m = int(min(w, h) * 0.05)
    draw.rounded_rectangle([m, m, w - m, h - m], radius=m,
                           fill=(0, 0, 0, 120), outline=(*accent, 230),
                           width=max(4, m // 2))
    # 타이틀 바
    draw.rounded_rectangle([m, m, w - m, int(h * 0.16)], radius=m,
                           fill=(*accent, 200))
    # 내부 슬롯 그리드
    gx0, gy0 = int(w * 0.10), int(h * 0.24)
    cell = int(min(w, h) * 0.12)
    for r in range(3):
        for c in range(5):
            x = gx0 + c * (cell + 10)
            y = gy0 + r * (cell + 10)
            if x + cell < w - m and y + cell < h - m:
                draw.rounded_rectangle([x, y, x + cell, y + cell], radius=6,
                                       fill=(255, 255, 255, 20),
                                       outline=(*accent, 120), width=2)


def _hud_bars(draw, w, h, colors) -> None:
    """HUD 바 세트 (체력/마나/경험치) + 미니맵 프레임."""
    accent = colors[2 if len(colors) > 2 else 0]
    red, blue = (200, 60, 60), (60, 120, 200)
    bx, bw = int(w * 0.06), int(w * 0.42)
    bar_h = int(h * 0.07)
    for i, (col, frac) in enumerate([(red, 0.8), (blue, 0.6), (accent, 0.45)]):
        y = int(h * 0.14) + i * int(bar_h * 1.6)
        draw.rounded_rectangle([bx, y, bx + bw, y + bar_h], radius=bar_h // 2,
                               fill=(0, 0, 0, 150), outline=(255, 255, 255, 60), width=2)
        draw.rounded_rectangle([bx, y, bx + int(bw * frac), y + bar_h],
                               radius=bar_h // 2, fill=(*col, 230))
    # 우측 미니맵 원형 프레임
    mr = int(min(w, h) * 0.3)
    cx, cy = int(w * 0.80), int(h * 0.42)
    draw.ellipse([cx - mr, cy - mr, cx + mr, cy + mr], fill=(0, 0, 0, 140),
                 outline=(*accent, 230), width=4)
    # 하단 스킬 슬롯
    sy = int(h * 0.78)
    sc = int(min(w, h) * 0.12)
    for i in range(5):
        x = bx + i * (sc + 10)
        draw.rounded_rectangle([x, sy, x + sc, sy + sc], radius=8,
                               fill=(255, 255, 255, 20), outline=(*accent, 150), width=2)


def _logo_text(img, draw, label, colors) -> None:
    w, h = img.size
    name = label.split("·")[0].strip()[:16]
    accent = colors[2 if len(colors) > 2 else 0]
    font = load_font(int(min(w, h) * 0.22), bold=True)
    bbox = draw.textbbox((0, 0), name, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (w - tw) // 2 - bbox[0], (h - th) // 2 - bbox[1]
    # 외곽선
    for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3)]:
        draw.text((x + dx, y + dy), name, font=font, fill=(*accent, 230))
    draw.text((x, y), name, font=font, fill=(245, 240, 230))


def _placeholder_vfx(size, label, palette) -> Image.Image:
    """검은 배경 위 발광 방사형 이펙트 (속성별 색상)."""
    from PIL import ImageFilter

    w, h = size
    col = _vfx_color(label, palette)
    img = Image.new("RGB", (w, h), (6, 5, 10))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = w // 2, h // 2
    # 중심 발광
    for r, a in [(int(min(w, h) * 0.42), 60), (int(min(w, h) * 0.30), 110),
                 (int(min(w, h) * 0.18), 200), (int(min(w, h) * 0.08), 255)]:
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*col, a))
    # 방사형 스파크
    rnd = _LCG(int(hashlib.md5(label.encode()).hexdigest(), 16))
    spikes = rnd.randint(8, 14)
    for i in range(spikes):
        ang = 2 * math.pi * i / spikes + rnd.random() * 0.3
        rr = int(min(w, h) * (0.28 + rnd.random() * 0.2))
        x2, y2 = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
        gd.line([cx, cy, x2, y2], fill=(*col, 180), width=max(2, w // 90))
        pr = max(2, w // 60)
        gd.ellipse([x2 - pr, y2 - pr, x2 + pr, y2 + pr], fill=(255, 255, 255, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(max(1, w // 160)))
    img.paste(Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB"), (0, 0))
    # 중심 하이라이트
    d = ImageDraw.Draw(img, "RGBA")
    hr = max(3, int(min(w, h) * 0.05))
    d.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=(255, 255, 255, 230))
    return img


def _placeholder_pixel(size, label, palette) -> Image.Image:
    """저해상도로 그린 뒤 nearest 확대 → 픽셀 아트 느낌."""
    w, h = size
    small = 24
    colors = [_hex(c) for c in (palette or ["#2E1A47", "#C89B3C"])]
    grid = Image.new("RGB", (small, small), colors[0])
    d = ImageDraw.Draw(grid)
    rnd = _LCG(int(hashlib.md5(label.encode()).hexdigest(), 16))
    # 좌우 대칭 캐릭터 실루엣
    body = colors[len(colors) // 2 if len(colors) > 1 else 0]
    for y in range(6, small - 3):
        width = rnd.randint(2, 6)
        for x in range(width):
            c = body if rnd.random() > 0.25 else colors[-1]
            d.point((small // 2 - x, y), fill=c)
            d.point((small // 2 + x, y), fill=c)
    # 머리
    d.rectangle([small // 2 - 3, 3, small // 2 + 3, 7], fill=colors[-1])
    return grid.resize((w, h), Image.NEAREST)


def _label_badge(img, draw, label) -> None:
    w, h = img.size
    text = (label[:34] + "…") if len(label) > 35 else label
    font = load_font(max(14, int(min(w, h) * 0.045)))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(th * 0.6)
    bx, by = int(w * 0.05), h - th - pad * 3
    draw.rounded_rectangle([bx, by, bx + tw + pad * 2, by + th + pad * 2],
                           radius=pad, fill=(0, 0, 0, 150))
    draw.text((bx + pad, by + pad - bbox[1]), text, font=font, fill=(255, 255, 255))


def _demo_mark(draw, w, h) -> None:
    f = load_font(max(12, int(min(w, h) * 0.035)))
    draw.text((int(w * 0.05), int(h * 0.04)), "DEMO", font=f, fill=(255, 255, 255, 210))


def _poly(cx, cy, r, n, rot):
    return [(cx + r * math.cos(rot + 2 * math.pi * i / n),
             cy + r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


class _LCG:
    def __init__(self, seed: int):
        self.s = seed & 0xFFFFFFFF

    def _n(self) -> int:
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s

    def randint(self, lo, hi):
        return lo if hi <= lo else lo + self._n() % (hi - lo + 1)

    def random(self):
        return self._n() / 0x7FFFFFFF
