"""스프라이트 시트(아틀라스) 패커.

다변형 에셋(표정/포즈/스킬 등)의 프레임들을 격자 아틀라스 PNG 한 장 +
프레임 좌표/피벗 메타데이터 JSON 으로 묶어 게임 엔진 임포트를 돕는다.
JSON 은 널리 쓰이는 형태(프레임 rect + pivot)로 출력한다.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image


def pack(
    frames: list[tuple[str, Path]],
    out_png: Path,
    out_json: Path,
    *,
    padding: int = 4,
) -> tuple[Path, Path] | None:
    """(라벨, 이미지경로) 목록을 아틀라스로 패킹.

    반환: (png_path, json_path) 또는 프레임이 없으면 None.
    """
    imgs: list[tuple[str, Image.Image]] = []
    for label, path in frames:
        if path and Path(path).exists():
            imgs.append((label, Image.open(path).convert("RGBA")))
    if not imgs:
        return None

    # 균일 셀(최대 프레임 크기)로 격자 배치
    cell_w = max(im.width for _, im in imgs)
    cell_h = max(im.height for _, im in imgs)
    n = len(imgs)
    cols = min(n, max(1, round(math.sqrt(n))))
    rows = math.ceil(n / cols)

    sheet_w = cols * cell_w + padding * (cols + 1)
    sheet_h = rows * cell_h + padding * (rows + 1)
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    meta_frames = []
    for i, (label, im) in enumerate(imgs):
        r, c = divmod(i, cols)
        x = padding + c * (cell_w + padding) + (cell_w - im.width) // 2
        y = padding + r * (cell_h + padding) + (cell_h - im.height) // 2
        sheet.paste(im, (x, y), im)
        meta_frames.append({
            "name": label,
            "frame": {"x": x, "y": y, "w": im.width, "h": im.height},
            "pivot": {"x": 0.5, "y": 1.0},  # 하단 중앙(캐릭터 기본)
        })

    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png, "PNG")

    doc = {
        "meta": {
            "image": out_png.name,
            "size": {"w": sheet_w, "h": sheet_h},
            "cell": {"w": cell_w, "h": cell_h},
            "columns": cols,
            "rows": rows,
            "format": "RGBA8888",
            "generator": "AXData Studio",
        },
        "frames": meta_frames,
    }
    out_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_png, out_json
