"""Gemini 서비스 — 캐릭터 아트 이미지 생성.

google-genai SDK 로 Gemini 이미지 모델(Nano Banana)을 호출한다.
GEMINI_API_KEY 가 없거나 호출이 실패하면 Pillow 로 스타일리시한
플레이스홀더 이미지를 생성한다(데모 모드).
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import Settings
from ..models import CharacterConcept
from .fonts import load_font


def generate_image(
    prompt: str,
    out_path: Path,
    size: tuple[int, int],
    settings: Settings,
    *,
    label: str = "",
    palette: list[str] | None = None,
) -> bool:
    """이미지를 생성해 out_path 에 저장. 실제 생성이면 True, 데모면 False 반환."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if settings.gemini_enabled:
        try:
            if _generate_with_gemini(prompt, out_path, size, settings):
                return True
        except Exception as exc:  # pragma: no cover - network/runtime guard
            print(f"[gemini_service] Gemini 호출 실패, 데모 폴백: {exc}")

    _generate_placeholder(out_path, size, label or prompt, palette)
    return False


def _generate_with_gemini(
    prompt: str, out_path: Path, size: tuple[int, int], settings: Settings
) -> bool:
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(
        model=settings.gemini_image_model,
        contents=prompt,
    )

    for candidate in resp.candidates or []:
        for part in candidate.content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                img = Image.open(_as_bytesio(inline.data)).convert("RGB")
                img = _fit(img, size)
                img.save(out_path)
                return True
    return False


def _as_bytesio(data):
    import io

    if isinstance(data, (bytes, bytearray)):
        return io.BytesIO(data)
    # 일부 SDK 버전은 base64 문자열을 반환
    import base64

    return io.BytesIO(base64.b64decode(data))


def _fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """비율 유지하며 목표 크기에 맞춰 크롭."""
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    iw, ih = img.size
    left, top = (iw - tw) // 2, (ih - th) // 2
    return img.crop((left, top, left + tw, top + th))


# ── 데모 플레이스홀더 생성 ────────────────────────────────────────────


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (80, 80, 100)


def _generate_placeholder(
    out_path: Path,
    size: tuple[int, int],
    label: str,
    palette: list[str] | None,
) -> None:
    """프롬프트 해시로 결정론적인, 보기 좋은 추상 아트를 생성."""
    w, h = size
    colors = [_hex_to_rgb(c) for c in (palette or ["#2E1A47", "#C89B3C", "#E6D5B8"])]
    seed = int(hashlib.md5(label.encode("utf-8")).hexdigest(), 16)

    # 대각선 그라데이션 배경
    img = Image.new("RGB", (w, h))
    c1, c2 = colors[0], colors[-1]
    for y in range(h):
        t = y / max(1, h - 1)
        row = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        for x in range(w):
            pass
        img.paste(Image.new("RGB", (w, 1), row), (0, y))

    draw = ImageDraw.Draw(img, "RGBA")

    # 기하학적 도형들 (해시 기반, 반복 가능)
    rnd = _LCG(seed)
    accent = colors[len(colors) // 2 if len(colors) > 2 else 0]
    for _ in range(14):
        cx, cy = rnd.randint(0, w), rnd.randint(0, h)
        r = rnd.randint(int(min(w, h) * 0.05), int(min(w, h) * 0.28))
        col = colors[rnd.randint(0, len(colors) - 1)]
        alpha = rnd.randint(40, 130)
        shape = rnd.randint(0, 2)
        box = [cx - r, cy - r, cx + r, cy + r]
        if shape == 0:
            draw.ellipse(box, fill=(*col, alpha))
        elif shape == 1:
            draw.rectangle(box, fill=(*col, alpha))
        else:
            pts = _polygon(cx, cy, r, rnd.randint(3, 6), rnd.random() * math.pi)
            draw.polygon(pts, fill=(*col, alpha))

    # 실루엣 (캐릭터 느낌)
    _draw_silhouette(draw, w, h, accent)

    # 라벨 배지
    _draw_label(img, draw, label)

    img.save(out_path)


def _draw_silhouette(draw, w, h, color) -> None:
    cx = w // 2
    head_r = int(min(w, h) * 0.10)
    head_y = int(h * 0.32)
    draw.ellipse(
        [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r],
        fill=(*color, 70),
    )
    body = [
        (cx - int(w * 0.18), h),
        (cx - int(w * 0.10), head_y + head_r),
        (cx + int(w * 0.10), head_y + head_r),
        (cx + int(w * 0.18), h),
    ]
    draw.polygon(body, fill=(*color, 70))


def _draw_label(img, draw, label: str) -> None:
    w, h = img.size
    text = (label[:38] + "…") if len(label) > 39 else label
    font = load_font(int(min(w, h) * 0.045))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(th * 0.6)
    bx0, by0 = int(w * 0.05), h - th - pad * 3
    draw.rounded_rectangle(
        [bx0, by0, bx0 + tw + pad * 2, by0 + th + pad * 2],
        radius=pad,
        fill=(0, 0, 0, 150),
    )
    draw.text((bx0 + pad, by0 + pad - bbox[1]), text, font=font, fill=(255, 255, 255))
    # "DEMO" 워터마크
    dfont = load_font(int(min(w, h) * 0.035))
    draw.text((int(w * 0.05), int(h * 0.04)), "DEMO", font=dfont, fill=(255, 255, 255, 200))


def _polygon(cx, cy, r, n, rot):
    return [
        (cx + r * math.cos(rot + 2 * math.pi * i / n),
         cy + r * math.sin(rot + 2 * math.pi * i / n))
        for i in range(n)
    ]


class _LCG:
    """작고 결정론적인 난수 생성기 (시드 기반 재현성)."""

    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF

    def _next(self) -> int:
        self.state = (1103515245 * self.state + 12345) & 0x7FFFFFFF
        return self.state

    def randint(self, lo: int, hi: int) -> int:
        if hi <= lo:
            return lo
        return lo + self._next() % (hi - lo + 1)

    def random(self) -> float:
        return self._next() / 0x7FFFFFFF


def generate_character_images(
    concept: CharacterConcept,
    job_dir: Path,
    settings: Settings,
) -> dict[str, tuple[Path, bool]]:
    """초상화 / 전신 / 아이콘 3종을 생성. {kind: (path, is_real)} 반환."""
    specs = {
        "portrait": (concept.image_prompts.portrait, (768, 768), "초상화"),
        "fullbody": (concept.image_prompts.fullbody, (768, 1024), "전신 스프라이트"),
        "icon": (concept.image_prompts.icon, (512, 512), "엠블럼 아이콘"),
    }
    results: dict[str, tuple[Path, bool]] = {}
    for kind, (prompt, size, label) in specs.items():
        path = job_dir / f"{kind}.png"
        is_real = generate_image(
            prompt, path, size, settings,
            label=f"{concept.name} · {label}",
            palette=concept.color_palette,
        )
        results[kind] = (path, is_real)
    return results
