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
# 대기(Idle) 호흡 프레임 합성
# ─────────────────────────────────────────────────────────────────────
def breathe(src: Path, dst: Path, phase: float, amp: float = 0.02) -> None:
    """기준 프레임 하나를 발(하단) 고정으로 미세하게 세로 확장해 호흡 프레임 생성.

    프레임마다 AI가 크기·구도를 다르게 그리는 흔들림을 없애기 위해, 대기
    애니메이션은 기준 1장에서 이 함수로 나머지 프레임을 만든다. phase 0~1 을
    한 주기로 (1-cos)/2 곡선을 써서 '확장만'(여백 없음) 하므로 은은한 호흡만
    남고 프레임 크기는 항상 동일하다.
    """
    import math

    img = Image.open(src)
    w, h = img.size
    factor = 1.0 + amp * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
    nh = max(h, round(h * factor))
    scaled = img.resize((w, nh), Image.LANCZOS)
    canvas = Image.new(img.mode, (w, h))
    canvas.paste(scaled, (0, h - nh))  # 하단 정렬(발 고정), 상단은 자연 크롭
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dst)


# ─────────────────────────────────────────────────────────────────────
# 등급(rarity) 프레임 후처리 — 등급별 테두리를 확실히 입혀 차이가 항상 보이게
# ─────────────────────────────────────────────────────────────────────
# 등급별 (테두리색 RGB, 굵기 배수). 뒤로 갈수록 굵고 화려하게.
_RARITY_FRAME = {
    "일반":  ((150, 150, 150), 0),   # 프레임 없음
    "고급":  ((200, 205, 210), 1),
    "희귀":  ((70, 140, 240), 2),
    "영웅":  ((165, 80, 230), 3),
    "전설":  ((240, 190, 60), 4),
    "초월":  ((80, 220, 220), 5),
    "멸망":  ((200, 40, 55), 5),
    "태초":  ((60, 200, 170), 6),
    "무아":  ((245, 240, 210), 7),
    "극":    ((255, 90, 210), 8),
}


def apply_rarity_frame(path: Path, rarity: str) -> None:
    """등급별 색·굵기의 테두리 프레임을 이미지 가장자리에 그려 다시 저장.

    AI 결과와 무관하게 등급 차이가 항상 드러나도록(‘꼭 지켜지도록’) 하는 후처리.
    '일반'은 프레임 없음. 고등급일수록 굵고 이중선+은은한 내부 글로우.
    """
    color, level = _RARITY_FRAME.get(rarity, ((150, 150, 150), 0))
    if level <= 0:
        return
    try:
        img = Image.open(path)
        mode = img.mode if img.mode in ("RGB", "RGBA") else "RGBA"
        img = img.convert(mode)
        w, h = img.size
        unit = max(2, round(min(w, h) / 200))     # 해상도 비례 기본 두께
        t = unit * level                            # 등급별 외곽선 두께
        draw = ImageDraw.Draw(img)
        outline = color + ((255,) if mode == "RGBA" else ())
        # 외곽 테두리(굵게)
        for i in range(t):
            draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=outline)
        # 고등급(≥4): 안쪽에 밝은 이중선 한 줄 추가(글로우 느낌)
        if level >= 4:
            inner = tuple(min(255, c + 60) for c in color)
            inner = inner + ((255,) if mode == "RGBA" else ())
            g = t + unit * 2
            draw.rectangle([g, g, w - 1 - g, h - 1 - g], outline=inner, width=max(1, unit))
        img.save(path)
    except Exception as exc:  # pragma: no cover - 방어
        log.warning("등급 프레임 적용 실패(원본 유지): %s", exc)


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
