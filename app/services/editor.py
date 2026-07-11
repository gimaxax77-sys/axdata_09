"""생성 결과 이미지 편집 — 크롭, 배경색 교체/투명, 밝기·대비·채도 보정.

각 연산은 잡 폴더 안의 이미지 파일 하나에 적용되어 제자리에 저장된다.
알파(투명)는 가능한 한 보존한다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance

from ..logging_config import get_logger
from . import imageops

log = get_logger(__name__)


def _hex(h: str) -> tuple[int, int, int]:
    h = (h or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (255, 255, 255)


def apply_edit(
    path: Path,
    *,
    crop: dict | None = None,
    bg: str | None = None,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
) -> tuple[int, int]:
    """이미지 파일에 편집을 적용하고 제자리 저장. 최종 크기 반환.

    crop: {l,t,r,b} 프랙션(0~1). 이미지 대비 상대 좌표.
    bg: '#RRGGBB' 단색 합성 또는 'transparent' 배경 제거. None 이면 변경 없음.
    brightness/contrast/saturation: 1.0 = 원본. 배율.
    """
    img = Image.open(path)

    if crop:
        img = _crop(img, crop)
    if bg is not None:
        img = _apply_bg(img, bg)
    if (brightness, contrast, saturation) != (1.0, 1.0, 1.0):
        img = _adjust(img, brightness, contrast, saturation)

    # .png 확장자이므로 알파 유지. RGB 로 합성된 경우도 그대로 저장.
    img.save(path)
    return img.size


def _crop(img: Image.Image, crop: dict) -> Image.Image:
    w, h = img.size
    l = int(float(crop.get("l", 0)) * w)
    t = int(float(crop.get("t", 0)) * h)
    r = int(float(crop.get("r", 1)) * w)
    b = int(float(crop.get("b", 1)) * h)
    l, t = max(0, min(l, w)), max(0, min(t, h))
    r, b = max(0, min(r, w)), max(0, min(b, h))
    if r - l < 4 or b - t < 4:   # 너무 작은 크롭은 무시
        return img
    return img.crop((l, t, r, b))


def _apply_bg(img: Image.Image, bg: str) -> Image.Image:
    if bg == "transparent":
        return imageops.remove_background(img.convert("RGB"))
    # 단색 배경 위에 합성 (알파 평탄화)
    rgba = img.convert("RGBA")
    base = Image.new("RGBA", rgba.size, (*_hex(bg), 255))
    return Image.alpha_composite(base, rgba).convert("RGB")


def _adjust(img: Image.Image, b: float, c: float, s: float) -> Image.Image:
    alpha = img.getchannel("A") if "A" in img.getbands() else None
    rgb = img.convert("RGB")
    if b != 1.0:
        rgb = ImageEnhance.Brightness(rgb).enhance(b)
    if c != 1.0:
        rgb = ImageEnhance.Contrast(rgb).enhance(c)
    if s != 1.0:
        rgb = ImageEnhance.Color(rgb).enhance(s)
    if alpha is not None:
        rgb = rgb.convert("RGBA")
        rgb.putalpha(alpha)
    return rgb
