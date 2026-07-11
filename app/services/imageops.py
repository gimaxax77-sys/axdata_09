"""이미지 후처리 — 배경 제거(투명 알파), 타일러블 처리, 리사이즈/크롭.
gemini_service 에서 분리(가독성).
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw

from ..logging_config import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────
# 배경 제거 (투명 알파)
# ─────────────────────────────────────────────────────────────────────
def make_transparent(path: Path) -> None:
    """파일을 읽어 배경을 제거하고 알파 PNG 로 다시 저장."""
    try:
        img = Image.open(path).convert("RGB")
        out = remove_background(img)
        out.save(path)  # .png 확장자이므로 알파 유지
    except Exception as exc:  # pragma: no cover - 방어
        log.warning("배경 제거 실패(원본 유지): %s", exc)


def remove_background(img: Image.Image) -> Image.Image:
    """배경 제거. rembg 가 있으면 사용, 없으면 코너 플러드필 폴백."""
    try:
        from rembg import remove  # type: ignore

        return remove(img.convert("RGBA"))
    except Exception:
        return flood_alpha(img)


def flood_alpha(img: Image.Image, tol: int = 42) -> Image.Image:
    """네 모서리에서 플러드필로 균일한 배경을 투명 처리 (의존성 없음).

    프롬프트가 'plain background' 를 요청하므로 배경이 대체로 균일하다는
    가정. 복잡/그라데이션 배경(데모 플레이스홀더 등)에는 효과가 약할 수 있다.
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    sentinel = (0, 254, 1)  # 실제로 잘 안 나오는 표식 색
    work = rgb.copy()
    for seed in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
                 (w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]:
        try:
            ImageDraw.floodfill(work, seed, sentinel, thresh=tol)
        except Exception:
            pass
    # sentinel 로 칠해진 영역 → 알파 0. numpy 가 있으면 벡터화(고해상에서 큰 이득),
    # 없으면 순수 파이썬 폴백.
    rgba = rgb.convert("RGBA")
    try:
        import numpy as np

        arr = np.asarray(work)  # (h, w, 3)
        mask = np.all(arr == np.array(sentinel, dtype=arr.dtype), axis=-1)
        alpha = np.where(mask, 0, 255).astype("uint8")
        alpha_img = Image.fromarray(alpha, mode="L")
    except Exception as exc:  # numpy 미설치/실패 → 순수 파이썬
        log.debug("numpy 알파 가속 미사용(%s), 파이썬 폴백", exc)
        alpha_data = [0 if p == sentinel else 255 for p in work.getdata()]
        alpha_img = Image.new("L", (w, h))
        alpha_img.putdata(alpha_data)
    rgba.putalpha(alpha_img)
    return rgba


# ─────────────────────────────────────────────────────────────────────
# 타일셋: 이음새 완화 + 타일 미리보기
# ─────────────────────────────────────────────────────────────────────
def apply_tileable(path: Path) -> None:
    """파일을 읽어 이음새를 완화(오프셋+시임 블렌드)해 다시 저장."""
    try:
        img = Image.open(path).convert("RGB")
        out = make_tileable(img)
        out.save(path)
    except Exception as exc:  # pragma: no cover
        log.warning("타일러블 처리 실패(원본 유지): %s", exc)


def make_tileable(img: Image.Image) -> Image.Image:
    """오프셋으로 이음새를 중앙에 모은 뒤 블러 블렌드로 완화."""
    from PIL import ImageFilter

    w, h = img.size
    off = Image.new("RGB", (w, h))
    for dx, dy in [(w // 2, h // 2), (w // 2 - w, h // 2),
                   (w // 2, h // 2 - h), (w // 2 - w, h // 2 - h)]:
        off.paste(img, (dx, dy))
    blurred = off.filter(ImageFilter.GaussianBlur(6))
    band = max(8, w // 12)
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([w // 2 - band, 0, w // 2 + band, h], fill=200)
    md.rectangle([0, h // 2 - band, w, h // 2 + band], fill=200)
    mask = mask.filter(ImageFilter.GaussianBlur(max(2, band // 2)))
    return Image.composite(blurred, off, mask)


def tile_preview_file(src: Path, out: Path, n: int = 3) -> Path | None:
    """타일을 n x n 으로 반복 배치한 미리보기 이미지 생성."""
    try:
        tile = Image.open(src).convert("RGB")
    except Exception:
        return None
    tw, th = tile.size
    # 미리보기가 너무 커지지 않게 타일 축소
    s = min(1.0, 256 / max(tw, th))
    if s < 1.0:
        tile = tile.resize((int(tw * s), int(th * s)), Image.LANCZOS)
        tw, th = tile.size
    canvas = Image.new("RGB", (tw * n, th * n))
    for r in range(n):
        for c in range(n):
            canvas.paste(tile, (c * tw, r * th))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


# ─────────────────────────────────────────────────────────────────────
# 디코드/리사이즈 유틸
# ─────────────────────────────────────────────────────────────────────
def as_bytesio(data):
    if isinstance(data, (bytes, bytearray)):
        return io.BytesIO(data)
    return io.BytesIO(base64.b64decode(data))


def fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    img = img.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    iw, ih = img.size
    left, top = (iw - tw) // 2, (ih - th) // 2
    return img.crop((left, top, left + tw, top + th))
