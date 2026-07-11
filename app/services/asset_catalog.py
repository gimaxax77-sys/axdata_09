"""에셋 카탈로그 — 생성 가능한 모든 아트 요소의 데이터 레지스트리.

각 에셋은 프롬프트 템플릿, 크기, 카테고리, 변형(variants), 적용 엔티티,
플레이스홀더 스타일을 갖는다. 파이프라인/Gemini/UI 가 이 레지스트리를
공통으로 참조하므로, 여기에 항목을 추가하면 전체에 반영된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 엔티티 타입
ENTITY_TYPES = {
    "character": "캐릭터",
    "monster": "몬스터",
    "npc": "NPC",
}

# 카테고리 (UI 그룹 및 표시 순서)
CATEGORIES = {
    "character": "캐릭터 아트",
    "item": "아이템 / 장비",
    "environment": "환경 / 배경",
    "ui": "UI / 브랜딩",
    "composite": "통합 산출물",
}

ALL_ENTITIES = frozenset(ENTITY_TYPES)


@dataclass(frozen=True)
class AssetSpec:
    key: str
    label: str
    category: str
    size: tuple[int, int]
    prompt: str                       # {visual} {name} {style} {genre} {variant} {kind}
    placeholder: str = "figure"       # figure|scene|emblem|pixel|card|logo
    variants: tuple[str, ...] = ()    # 비어있으면 단일 이미지
    entities: frozenset = ALL_ENTITIES
    default: bool = False
    is_image: bool = True             # False = 합성 산출물(sheet/video)
    desc: str = ""


# ─────────────────────────────────────────────────────────────────────
# 카탈로그 정의
# ─────────────────────────────────────────────────────────────────────
_SPECS: list[AssetSpec] = [
    # ── 캐릭터 아트 ───────────────────────────────────────────────
    AssetSpec(
        "portrait", "초상화", "character", (768, 768),
        "head and shoulders portrait of {name}, {visual}, {style}, "
        "dramatic rim lighting, detailed face, clean plain background",
        placeholder="figure", default=True,
        desc="대화창·프로필용 얼굴 클로즈업",
    ),
    AssetSpec(
        "fullbody", "전신", "character", (768, 1024),
        "full body character art of {name}, {visual}, {style}, "
        "dynamic hero pose, full figure visible, plain neutral background",
        placeholder="figure", default=True,
        desc="인게임 캐릭터·도감용 전신",
    ),
    AssetSpec(
        "expressions", "표정 세트", "character", (512, 512),
        "portrait of {name} showing a clear {variant} facial expression, "
        "{visual}, {style}, consistent character design, plain background",
        placeholder="figure",
        variants=("기쁨", "분노", "슬픔", "놀람"),
        desc="비주얼노벨·대화 시스템용 감정 표정",
    ),
    AssetSpec(
        "poses", "액션 포즈", "character", (768, 768),
        "full body action pose of {name} performing a {variant} motion, "
        "{visual}, {style}, dynamic, plain background",
        placeholder="figure",
        variants=("공격", "방어", "승리"),
        desc="공격·방어·승리 모션 스틸",
    ),
    AssetSpec(
        "pixel_sprite", "도트 스프라이트", "character", (512, 512),
        "16-bit pixel art game sprite of {name}, {visual}, side view, "
        "clean pixel art, {genre} game, plain background",
        placeholder="pixel",
        desc="2D 게임용 픽셀 스프라이트",
    ),
    AssetSpec(
        "turnaround", "턴어라운드", "character", (640, 768),
        "character turnaround reference of {name}, {variant} view, {visual}, "
        "{style}, model sheet, consistent proportions, plain background",
        placeholder="figure",
        variants=("정면", "측면", "후면"),
        desc="정면·측면·후면 모델 시트",
    ),
    AssetSpec(
        "emblem", "엠블럼 아이콘", "character", (512, 512),
        "minimal emblem icon representing {name}, {visual} theme, "
        "{genre} crest, flat vector, centered, plain background",
        placeholder="emblem", default=True,
        desc="문장·심볼 아이콘",
    ),

    # ── 아이템 / 장비 ─────────────────────────────────────────────
    AssetSpec(
        "weapon_icons", "무기/방어구 아이콘", "item", (512, 512),
        "game item icon of the {variant} of {name}, {visual} theme, "
        "{genre}, detailed item icon, centered, plain background",
        placeholder="emblem",
        variants=("주무기", "보조 장비", "방어구"),
        entities=frozenset({"character", "npc"}),
        desc="주무기·보조장비·방어구 아이콘",
    ),
    AssetSpec(
        "item_grid", "인벤토리 아이템", "item", (768, 768),
        "grid of {genre} game inventory items related to {name}, {visual} theme, "
        "consumables and materials, item icons on a subtle grid, plain background",
        placeholder="emblem",
        desc="소비/재료 아이템 그리드",
    ),
    AssetSpec(
        "skill_icons", "스킬 아이콘", "item", (512, 512),
        "ability skill icon for {name}'s {variant}, {visual} theme, "
        "{genre} spell effect, glowing, centered, plain background",
        placeholder="emblem",
        variants=("스킬 I", "스킬 II", "궁극기"),
        desc="스킬·이펙트 아이콘",
    ),

    # ── 환경 / 배경 ───────────────────────────────────────────────
    AssetSpec(
        "background", "배경 일러스트", "environment", (1280, 720),
        "wide environment concept art of the world of {name}, {genre} setting, "
        "{visual} mood and palette, cinematic landscape, no characters, atmospheric",
        placeholder="scene",
        desc="스테이지 배경·컷신",
    ),
    AssetSpec(
        "tileset", "타일셋", "environment", (768, 768),
        "seamless {genre} game tileset related to {name}'s environment, "
        "{visual} theme, top-down tiles, terrain and props, grid layout",
        placeholder="scene",
        desc="맵 타일·프롭",
    ),

    # ── UI / 브랜딩 ───────────────────────────────────────────────
    AssetSpec(
        "logo", "타이틀 로고", "ui", (1024, 512),
        "game title logo for '{name}', {genre} style emblem logotype, "
        "{visual} color theme, decorative, plain dark background",
        placeholder="logo",
        desc="이름 기반 타이틀 로고",
    ),
    AssetSpec(
        "card_frame", "TCG 카드", "ui", (768, 1024),
        "trading card game card featuring {name}, {visual}, {style}, "
        "ornate {genre} card frame border, name banner at top, stat corners",
        placeholder="card",
        desc="카드 아트 + 프레임",
    ),
    AssetSpec(
        "banner", "배너 / 썸네일", "ui", (1280, 512),
        "wide promotional banner of {name}, {visual}, {style}, "
        "{genre}, cinematic composition, space for title text",
        placeholder="scene",
        desc="홍보 배너·썸네일",
    ),

    # ── 통합 산출물 ───────────────────────────────────────────────
    AssetSpec(
        "sheet", "캐릭터 시트 (PNG/PDF)", "composite", (0, 0), "",
        default=True, is_image=False,
        desc="아트 + 스탯 + 설정 통합 문서",
    ),
    AssetSpec(
        "video", "쇼케이스 영상 (GIF/MP4) + CapCut", "composite", (0, 0), "",
        default=True, is_image=False,
        desc="Ken Burns 슬라이드쇼 + CapCut draft",
    ),
]

CATALOG: dict[str, AssetSpec] = {s.key: s for s in _SPECS}


def specs_for_entity(entity_type: str) -> list[AssetSpec]:
    return [s for s in _SPECS if entity_type in s.entities]


def default_keys(entity_type: str) -> list[str]:
    return [s.key for s in specs_for_entity(entity_type) if s.default]


def catalog_payload() -> dict:
    """프론트엔드용 카탈로그 직렬화."""
    return {
        "entity_types": ENTITY_TYPES,
        "categories": CATEGORIES,
        "assets": [
            {
                "key": s.key,
                "label": s.label,
                "category": s.category,
                "variants": list(s.variants),
                "entities": sorted(s.entities),
                "default": s.default,
                "is_image": s.is_image,
                "desc": s.desc,
            }
            for s in _SPECS
        ],
    }


def build_prompt(spec: AssetSpec, *, visual: str, name: str, style: str,
                 genre: str, variant: str = "") -> str:
    """스펙 템플릿에서 프롬프트를 조합 (누락 키 무시)."""
    fields = {
        "visual": visual, "name": name, "style": style,
        "genre": genre, "variant": variant, "kind": spec.label,
    }
    return _safe_format(spec.prompt, fields)


def _safe_format(template: str, fields: dict) -> str:
    out = template
    for k, v in fields.items():
        out = out.replace("{" + k + "}", str(v))
    return out
