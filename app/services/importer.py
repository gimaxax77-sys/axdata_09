"""CSV / 스프레드시트 가져오기 — 표에서 생성 계획을 분석해 자동 설정.

사용자가 표준 양식(각 행 = 한 개체)을 채워 올리면, 각 행을 분석해
필요한 아트 에셋을 자동으로 정하고(용도 기반) 생성 요청으로 변환한다.

CSV 는 기본 지원, .xlsx 는 openpyxl 이 설치돼 있으면 지원한다.
"""
from __future__ import annotations

import csv
import io

from . import asset_catalog as cat

MAX_ROWS = 50  # 폭주 방지 상한


# ─────────────────────────────────────────────────────────────────────
# 용도(purpose) → 에셋 번들 (내용 분석 자동 설정)
# ─────────────────────────────────────────────────────────────────────
PURPOSE_BUNDLES: dict[str, list[str]] = {
    "rpg": ["portrait", "fullbody", "expressions", "poses", "sheet"],
    "카드": ["portrait", "card_frame", "splash", "emblem"],
    "카드게임": ["portrait", "card_frame", "splash", "emblem"],
    "tcg": ["portrait", "card_frame", "splash", "emblem"],
    "2d": ["pixel_sprite", "anim_idle", "anim_walk", "anim_attack"],
    "도트": ["pixel_sprite", "anim_idle", "anim_walk", "anim_attack"],
    "픽셀": ["pixel_sprite", "anim_idle", "anim_walk", "anim_attack"],
    "플랫포머": ["pixel_sprite", "anim_idle", "anim_walk", "anim_attack"],
    "도감": ["portrait", "fullbody", "emblem", "sheet"],
    "컬렉션": ["portrait", "fullbody", "emblem", "sheet"],
    "프로필": ["portrait", "namecard", "emote"],
    "sns": ["portrait", "namecard", "emote"],
    "ui": ["ui_buttons", "ui_icons", "ui_currency", "ui_panel", "ui_hud"],
    "인터페이스": ["ui_buttons", "ui_icons", "ui_currency", "ui_panel", "ui_hud"],
    "풀세트": ["portrait", "fullbody", "expressions", "poses", "emblem", "sheet"],
    "전체": ["portrait", "fullbody", "expressions", "poses", "emblem", "sheet"],
    "기본": ["portrait", "fullbody", "sheet"],
}
DEFAULT_BUNDLE = ["portrait", "fullbody", "sheet"]


# ─────────────────────────────────────────────────────────────────────
# 헤더 별칭 (한/영 혼용 허용) → 표준 필드
# ─────────────────────────────────────────────────────────────────────
_HEADER_ALIASES = {
    "entity_type": ["entity_type", "타입", "종류", "유형", "entity", "type"],
    "name": ["name", "이름", "명칭"],
    "role": ["role", "직업", "종족", "역할", "유형2", "job", "class"],
    "genre": ["genre", "장르"],
    "art_style": ["art_style", "아트스타일", "스타일", "style", "artstyle"],
    "keywords": ["keywords", "키워드", "특징", "설명", "keyword"],
    "assets": ["assets", "에셋", "요소", "asset", "산출물"],
    "purpose": ["purpose", "용도", "목적", "프리셋", "번들"],
    "variant_count": ["variant_count", "변형수", "변형", "장수", "variants"],
    "image_scale": ["image_scale", "배율", "크기", "scale"],
    "transparent": ["transparent", "투명", "투명배경"],
}

_ENTITY_ALIASES = {
    "character": ["character", "캐릭터", "케릭터", "플레이어", "주인공", "char"],
    "monster": ["monster", "몬스터", "적", "보스", "mob"],
    "npc": ["npc", "엔피씨", "엔피시", "논플레이어"],
}

# 한글 라벨 → 에셋 키 (사용자가 '초상화' 처럼 라벨로 적어도 인식)
_KEY_BY_LABEL = {s.label: s.key for s in cat._SPECS}
_VALID_KEYS = {s.key for s in cat._SPECS}

# 장르 한글 라벨 → 키
_GENRE_BY_LABEL = {v: k for k, v in cat.GENRES.items()}


def _norm(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _truthy(v: str) -> bool:
    return _norm(v) in {"y", "yes", "예", "true", "1", "o", "on", "투명", "t"}


def _map_header(raw: str) -> str | None:
    n = _norm(raw)
    for field, aliases in _HEADER_ALIASES.items():
        if n in {_norm(a) for a in aliases}:
            return field
    return None


def _map_entity(v: str) -> str:
    n = _norm(v)
    for key, aliases in _ENTITY_ALIASES.items():
        if n in {_norm(a) for a in aliases}:
            return key
    return "character"


def _map_genre(v: str) -> str:
    v = (v or "").strip()
    if v in cat.GENRES:
        return v
    if v in _GENRE_BY_LABEL:
        return _GENRE_BY_LABEL[v]
    n = _norm(v)
    for k in cat.GENRES:
        if _norm(k) == n:
            return k
    return "fantasy"


def _resolve_assets(assets_cell: str, purpose_cell: str, entity: str,
                    warnings: list[str]) -> list[str]:
    """에셋 셀(직접 지정) 우선, 없으면 용도(purpose) 번들, 그래도 없으면 기본."""
    valid_for_entity = {s.key for s in cat.specs_for_entity(entity)}

    def clean(keys: list[str]) -> list[str]:
        out, seen = [], set()
        for k in keys:
            k = k.strip()
            if not k:
                continue
            key = k if k in _VALID_KEYS else _KEY_BY_LABEL.get(k)
            if key is None:
                warnings.append(f"알 수 없는 에셋 '{k}' 무시")
                continue
            if key not in valid_for_entity:
                warnings.append(f"'{key}' 는 {entity} 에 없어 제외")
                continue
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out

    if assets_cell.strip():
        # 셀 안 구분자: , ; | 모두 허용
        raw = assets_cell.replace(";", ",").replace("|", ",").split(",")
        keys = clean(raw)
        if keys:
            return keys
        warnings.append("에셋 셀에서 유효한 항목을 못 찾아 용도/기본으로 대체")

    p = _norm(purpose_cell)
    if p:
        for name, bundle in PURPOSE_BUNDLES.items():
            if _norm(name) == p or _norm(name) in p:
                return clean(list(bundle))
        warnings.append(f"알 수 없는 용도 '{purpose_cell}' — 기본 세트 사용")
    return clean(list(DEFAULT_BUNDLE))


def parse_upload(filename: str, content: bytes) -> list[dict]:
    """업로드 파일을 행 딕셔너리 목록으로 파싱 (CSV 기본, xlsx 선택)."""
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        return _parse_xlsx(content)
    return _parse_csv(content)


def _parse_csv(content: bytes) -> list[dict]:
    text = _decode(content)
    # 주석/빈 줄 제거
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        return []
    reader = csv.reader(lines)
    rows = list(reader)
    return _rows_to_dicts(rows)


def _parse_xlsx(content: bytes) -> list[dict]:
    try:
        import openpyxl  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "xlsx 를 읽으려면 openpyxl 이 필요합니다. CSV 로 저장해 올리거나 "
            "`pip install openpyxl` 후 다시 시도하세요."
        ) from exc
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows = [[("" if c is None else str(c)) for c in row]
            for row in ws.iter_rows(values_only=True)]
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    return _rows_to_dicts(rows)


def _rows_to_dicts(rows: list[list[str]]) -> list[dict]:
    if not rows:
        return []
    header = rows[0]
    fields = [_map_header(h) for h in header]
    out = []
    for r in rows[1:]:
        d: dict = {}
        for i, field in enumerate(fields):
            if field and i < len(r):
                d[field] = str(r[i]).strip()
        if any(d.values()):
            out.append(d)
    return out


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def analyze(rows: list[dict]) -> dict:
    """행들을 분석해 생성 계획으로 변환. 미리보기/검증용."""
    plans = []
    truncated = len(rows) > MAX_ROWS
    for raw in rows[:MAX_ROWS]:
        warnings: list[str] = []
        entity = _map_entity(raw.get("entity_type", ""))
        genre = _map_genre(raw.get("genre", ""))
        assets = _resolve_assets(raw.get("assets", ""), raw.get("purpose", ""),
                                 entity, warnings)
        try:
            vc = int(float(raw.get("variant_count") or 5))
        except (TypeError, ValueError):
            vc = 5
        vc = max(1, min(10, vc))
        try:
            scale = float(raw.get("image_scale") or 1.0)
        except (TypeError, ValueError):
            scale = 1.0
        scale = max(0.5, min(2.0, scale))
        plans.append({
            "entity_type": entity,
            "name": raw.get("name", "").strip(),
            "role": raw.get("role", "").strip(),
            "genre": genre,
            "art_style": raw.get("art_style", "").strip() or "semi-realistic digital painting",
            "keywords": raw.get("keywords", "").strip(),
            "assets": assets,
            "variant_count": vc,
            "image_scale": scale,
            "transparent": _truthy(raw.get("transparent", "")),
            "warnings": warnings,
        })
    return {"plans": plans, "truncated": truncated, "total": len(rows)}


# 표준 양식 CSV (헤더 + 안내 주석 + 예시 행)
TEMPLATE_CSV = """\
# AXData Studio 아트 제작 표준 양식 — 각 행 = 한 개체(캐릭터/몬스터/NPC)
# '용도' 에 rpg / 카드 / 2d / 도감 / 프로필 / ui / 풀세트 중 하나를 적으면 필요한 에셋이 자동 선택됩니다.
# '에셋' 에 직접 키를 적으면(구분자 ; ) 용도보다 우선합니다. 예: portrait;fullbody;emblem
# 이름을 비우면 GPT가 자동 작명합니다. 투명은 y/n. '#' 로 시작하는 줄은 무시됩니다.
타입,이름,직업,장르,아트스타일,키워드,에셋,용도,변형수,배율,투명
캐릭터,카엘,검사,fantasy,anime cel shading,붉은 갑옷·대검,,rpg,5,1.0,n
몬스터,,화염 드래곤,fantasy,dark fantasy concept art,용암·날개,,도감,3,1.0,y
NPC,미라,상인,fantasy,,친절한 미소,portrait;namecard;emote,,5,1.0,n
캐릭터,,궁수,fantasy,pixel art,초록 후드,,2d,4,1.0,y
"""
