"""Gemini 서비스 — 임의 아트 에셋 이미지 생성.

google-genai SDK 로 Gemini 이미지 모델(Nano Banana)을 호출한다.
GEMINI_API_KEY 가 없거나 호출이 실패하면 Pillow 로 카테고리별
플레이스홀더 이미지를 생성한다(데모 모드).
"""
from __future__ import annotations

import base64
import hashlib
import io
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from ..config import Settings
from ..models import EntityConcept
from . import asset_catalog as cat
from .fonts import load_font


@dataclass
class ImageResult:
    path: Path
    label: str
    demo: bool
    variant: str = ""


# ─────────────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────────────
def generate_asset(
    spec: cat.AssetSpec,
    concept: EntityConcept,
    job_dir: Path,
    settings: Settings,
) -> list[ImageResult]:
    """스펙 하나에 대한 이미지(들)를 생성. 다변형이면 여러 장."""
    variants = spec.variants or ("",)
    results: list[ImageResult] = []
    for i, variant in enumerate(variants):
        prompt = cat.build_prompt(
            spec,
            visual=concept.visual_core,
            name=concept.name,
            style="",  # style 은 art_style 대신 visual_core 에 녹아 있음
            genre=concept.genre,
            variant=variant,
        )
        suffix = f"_{i+1}" if spec.variants else ""
        out = job_dir / f"{spec.key}{suffix}.png"
        label = f"{spec.label} · {variant}" if variant else spec.label
        is_real = _generate_image(
            prompt, out, spec.size, settings,
            placeholder=spec.placeholder,
            label=f"{concept.name}" + (f" · {variant}" if variant else f" · {spec.label}"),
            palette=concept.color_palette,
        )
        results.append(ImageResult(path=out, label=label, demo=not is_real, variant=variant))
    return results


def _generate_image(prompt, out_path, size, settings, *, placeholder, label, palette) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if settings.gemini_enabled:
        try:
            if _generate_with_gemini(prompt, out_path, size, settings):
                return True
        except Exception as exc:  # pragma: no cover - network guard
            print(f"[gemini_service] Gemini 호출 실패, 데모 폴백: {exc}")
    _generate_placeholder(out_path, size, label, palette, placeholder)
    return False


def _generate_with_gemini(prompt, out_path, size, settings) -> bool:
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_image_model, contents=prompt
    )
    for candidate in resp.candidates or []:
        for part in candidate.content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                img = Image.open(_as_bytesio(inline.data)).convert("RGB")
                _fit(img, size).save(out_path)
                return True
    return False


def _as_bytesio(data):
    if isinstance(data, (bytes, bytearray)):
        return io.BytesIO(data)
    return io.BytesIO(base64.b64decode(data))


def _fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    iw, ih = img.size
    left, top = (iw - tw) // 2, (ih - th) // 2
    return img.crop((left, top, left + tw, top + th))


# ─────────────────────────────────────────────────────────────────────
# 데모 플레이스홀더 (카테고리별 스타일)
# ─────────────────────────────────────────────────────────────────────
def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (80, 80, 100)


def _generate_placeholder(out_path, size, label, palette, style) -> None:
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
