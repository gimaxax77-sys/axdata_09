"""캐릭터 시트 컴포저.

생성된 아트와 GPT 기획서를 하나의 캐릭터 시트 이미지(PNG)로 조합하고,
동일 레이아웃을 PDF 로도 내보낸다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from ..models import EntityConcept
from .fonts import load_font

# A4 세로 비율에 가까운 캔버스
W, H = 1240, 1754
MARGIN = 60
BG = (18, 16, 28)
CARD = (30, 27, 45)
INK = (232, 228, 240)
SUB = (168, 162, 190)

# 엔티티별 섹션 라벨 (외형/성격/배경)
_SECTION_LABELS = {
    "character": ("외형", "성격", "배경 이야기"),
    "monster": ("외형", "행동 양식", "서식지 · 전승"),
    "npc": ("외형", "성향", "배경"),
}


def _load_rgb(path, bg=CARD):
    """이미지를 RGB 로 로드. 투명(RGBA) 이면 배경색 bg 위에 합성해
    시트에서 투명 영역이 검게 보이지 않도록 한다."""
    im = Image.open(path)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        base = Image.new("RGB", im.size, bg)
        base.paste(im, (0, 0), im)
        return base
    return im.convert("RGB")


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (200, 155, 60)


def _wrap(draw, text, font, max_w) -> list[str]:
    """문자 단위 + 단어 단위 혼합 줄바꿈 (한글/영문 모두 대응)."""
    if not text:
        return []
    lines: list[str] = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            trial = cur + ch
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = ch
        lines.append(cur)
    return lines


def _text_block(draw, xy, text, font, fill, max_w, line_gap=8, max_lines=0) -> int:
    x, y = xy
    lines = _wrap(draw, text, font, max_w)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        # 마지막 줄에 말줄임표
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_w:
            last = last[:-1]
        lines[-1] = last + "…"
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def compose_sheet(
    concept: EntityConcept,
    images: dict[str, Path],
    out_png: Path,
    out_pdf: Path | None = None,
) -> tuple[Path, Path | None]:
    accent = _hex_to_rgb(concept.color_palette[2] if len(concept.color_palette) > 2
                         else (concept.color_palette[0] if concept.color_palette else "#C89B3C"))

    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_title = load_font(64, bold=True)
    f_sub = load_font(30)
    f_h = load_font(30, bold=True)
    f_body = load_font(24)
    f_small = load_font(22)
    f_stat = load_font(24, bold=True)

    # ── 헤더 ─────────────────────────────────────────────
    from . import asset_catalog as cat
    entity_label = cat.ENTITY_TYPES.get(concept.entity_type, "캐릭터")
    draw.rectangle([0, 0, W, 170], fill=CARD)
    draw.rectangle([0, 170, W, 176], fill=accent)
    draw.text((MARGIN, 40), concept.name or "이름 없는 영웅", font=f_title, fill=INK)
    subtitle = " · ".join(x for x in [concept.title, concept.role, concept.genre] if x)
    draw.text((MARGIN, 118), subtitle, font=f_sub, fill=accent)
    # 엔티티 타입 배지 (우상단)
    badge = load_font(24, bold=True)
    bw = draw.textlength(entity_label, font=badge)
    draw.rounded_rectangle([W - MARGIN - bw - 32, 44, W - MARGIN, 92],
                           radius=14, fill=accent)
    draw.text((W - MARGIN - bw - 16, 52), entity_label, font=badge, fill=(20, 18, 30))

    # ── 좌측: 초상화 + 스탯 ──────────────────────────────
    col_x = MARGIN
    y = 210
    portrait = images.get("portrait")
    if portrait and portrait.exists():
        p = _load_rgb(portrait).resize((480, 480), Image.LANCZOS)
        img.paste(_rounded(p, 24), (col_x, y), _rounded_mask(480, 480, 24))
    y += 480 + 30

    # 스탯 바
    draw.text((col_x, y), "STATS", font=f_h, fill=accent)
    y += 46
    bar_w = 480
    for st in concept.stats:
        draw.text((col_x, y), st.name, font=f_stat, fill=INK)
        val_txt = str(st.value)
        draw.text((col_x + bar_w - draw.textlength(val_txt, font=f_stat), y),
                  val_txt, font=f_stat, fill=SUB)
        y += 34
        draw.rounded_rectangle([col_x, y, col_x + bar_w, y + 16], radius=8, fill=(50, 46, 70))
        fill_w = int(bar_w * st.value / 100)
        if fill_w > 16:
            draw.rounded_rectangle([col_x, y, col_x + fill_w, y + 16], radius=8, fill=accent)
        y += 40

    # 컬러 팔레트
    y += 6
    draw.text((col_x, y), "PALETTE", font=f_h, fill=accent)
    y += 44
    sw = 60
    for i, hexc in enumerate(concept.color_palette[:5]):
        bx = col_x + i * (sw + 12)
        draw.rounded_rectangle([bx, y, bx + sw, y + sw], radius=10,
                               fill=_hex_to_rgb(hexc), outline=(60, 56, 80))
    y += sw + 20

    # ── 우측: 텍스트 정보 ────────────────────────────────
    rx = MARGIN + 480 + 50
    rw = W - rx - MARGIN
    ry = 210

    # 우측 컬럼은 하단 썸네일 밴드(fy=H-400)를 침범하지 않도록 제한한다.
    BOTTOM = H - 430

    if concept.tagline:
        for line in _wrap(draw, f'“{concept.tagline}”', load_font(28), rw)[:2]:
            draw.text((rx, ry), line, font=load_font(28), fill=accent)
            ry += 40
        ry += 14

    def section(title: str, text: str, ry: int, max_lines: int) -> int:
        if ry > BOTTOM:
            return ry
        draw.text((rx, ry), title, font=f_h, fill=accent)
        ry += 42
        ry = _text_block(draw, (rx, ry), text, f_body, INK, rw, max_lines=max_lines)
        return ry + 22

    s_look, s_mind, s_back = _SECTION_LABELS.get(concept.entity_type,
                                                 _SECTION_LABELS["character"])
    ry = section(s_look, concept.appearance, ry, 3)
    ry = section(s_mind, concept.personality, ry, 3)
    ry = section(s_back, concept.backstory, ry, 4)

    # 능력 / 공격 패턴
    ability_label = "공격 패턴" if concept.entity_type == "monster" else "시그니처 능력"
    if ry <= BOTTOM:
        draw.text((rx, ry), ability_label, font=f_h, fill=accent)
        ry += 44
        for ab in concept.abilities[:5]:
            if ry > BOTTOM:
                break
            draw.ellipse([rx, ry + 8, rx + 10, ry + 18], fill=accent)
            _text_block(draw, (rx + 24, ry), ab, f_body, INK, rw - 24, max_lines=1)
            ry += f_body.size + 16

    # 엔티티별 부가 정보 (위협도/서식지, 직업/소속 등)
    if concept.extra and ry <= BOTTOM:
        ry += 14
        draw.text((rx, ry), "INFO", font=f_h, fill=accent)
        ry += 46
        for item in concept.extra[:4]:
            if ry > BOTTOM:
                break
            draw.text((rx, ry), f"{item.label}", font=load_font(21, bold=True), fill=accent)
            lbl_w = draw.textlength(f"{item.label}", font=load_font(21, bold=True))
            # 라벨과 값을 같은 줄에 두되, 길면 다음 줄로
            val_x = rx + max(140, lbl_w + 24)
            if draw.textlength(item.value, font=f_small) <= rw - (val_x - rx):
                draw.text((val_x, ry + 1), item.value, font=f_small, fill=INK)
                ry += 34
            else:
                ry += 30
                ry = _text_block(draw, (rx + 16, ry), item.value, f_small, INK, rw - 16, line_gap=4)
                ry += 8

    # ── 하단: 전신 + 아이콘 썸네일 ───────────────────────
    fy = H - 400
    draw.rectangle([0, fy - 30, W, fy - 26], fill=(50, 46, 70))
    fullbody = images.get("fullbody")
    if fullbody and fullbody.exists():
        fb = _load_rgb(fullbody)
        fb = _fit_thumb(fb, (228, 300))
        img.paste(fb, (MARGIN, fy))
        draw.text((MARGIN, fy + 306), "전신 / 스프라이트", font=f_small, fill=SUB)

    icon = images.get("icon")
    if icon and icon.exists():
        ic = _load_rgb(icon).resize((200, 200), Image.LANCZOS)
        img.paste(_rounded(ic, 16), (MARGIN + 290, fy), _rounded_mask(200, 200, 16))
        draw.text((MARGIN + 290, fy + 206), "엠블럼", font=f_small, fill=SUB)

    # 푸터
    draw.text((MARGIN, H - 44), "Generated by AXData Studio · GPT + Gemini + CapCut",
              font=load_font(18), fill=(110, 105, 130))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, "PNG")

    pdf_path = None
    if out_pdf is not None:
        img.convert("RGB").save(out_pdf, "PDF", resolution=150.0)
        pdf_path = out_pdf

    return out_png, pdf_path


# ── 이미지 유틸 ───────────────────────────────────────────


def _rounded_mask(w: int, h: int, r: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=r, fill=255)
    return mask


def _rounded(im: Image.Image, r: int) -> Image.Image:
    return im


def _fit_thumb(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    iw, ih = im.size
    scale = max(tw / iw, th / ih)
    im = im.resize((int(iw * scale), int(ih * scale)), Image.LANCZOS)
    iw, ih = im.size
    left, top = (iw - tw) // 2, (ih - th) // 2
    return im.crop((left, top, left + tw, top + th))
