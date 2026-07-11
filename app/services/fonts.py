"""폰트 로딩 헬퍼.

시스템에 설치된 TrueType 폰트를 찾아 사용하고(한글 지원 우선),
없으면 Pillow 기본 비트맵 폰트로 폴백한다. 결과 캐싱.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

# 한글 지원 폰트를 우선 탐색
_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
    "C:/Windows/Fonts/malgun.ttf",  # Windows
]

_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/malgunbd.ttf",
]


@lru_cache(maxsize=1)
def _find_font_path(bold: bool = False) -> str | None:
    candidates = _BOLD_CANDIDATES + _CANDIDATES if bold else _CANDIDATES
    for path in candidates:
        if Path(path).exists():
            return path
    return None


@lru_cache(maxsize=64)
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_font_path(bold)
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def has_truetype() -> bool:
    return _find_font_path() is not None
