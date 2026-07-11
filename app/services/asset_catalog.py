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
    "hud": "인게임 UI / HUD",
    "composite": "통합 산출물",
}

# 장르 (UI 드롭다운). 실제 API 는 모든 장르를 프롬프트에 반영한다.
GENRES = {
    "fantasy": "판타지",
    "sci-fi": "SF",
    "cyberpunk": "사이버펑크",
    "wuxia": "무협",
    "steampunk": "스팀펑크",
    "fairytale": "동화풍",
    "horror": "호러",
    "post-apoc": "포스트아포칼립스",
}

# 이미지 모델 선택지 (value, 표시명). 빈 값 = 서버 기본(.env)
IMAGE_MODELS = [
    {"value": "", "label": "기본 (서버 설정)"},
    {"value": "gemini-2.5-flash-image", "label": "Gemini 2.5 Flash Image (Nano Banana)"},
    {"value": "gpt-image-1", "label": "OpenAI gpt-image-1 (네이티브 투명)"},
]

# 아트 스타일 프리셋 (자유 입력도 가능)
ART_STYLES = [
    "semi-realistic digital painting",
    "anime cel shading",
    "watercolor illustration",
    "oil painting",
    "3D render",
    "pixel art",
    "cartoon / cel-shaded",
    "dark fantasy concept art",
    "cinematic concept art",
    "chibi / cute",
    "comic / ink",
]

ALL_ENTITIES = frozenset(ENTITY_TYPES)

# 동일 캐릭터로 보여야 하는 에셋(앵커 이미지를 레퍼런스로 사용)
_CHAR_REF_KEYS = frozenset({
    "portrait", "fullbody", "expressions", "poses", "turnaround",
    "pixel_sprite", "card_frame", "splash", "namecard",
})
# 배경 제거(투명 알파) 대상 — 스프라이트/아이콘 컷아웃
_CUTOUT_KEYS = frozenset({
    "portrait", "fullbody", "expressions", "poses", "turnaround",
    "pixel_sprite", "emblem", "emote", "companion",
    "weapon_icons", "item_grid", "skill_icons", "rarity_frame",
    "ui_icons", "ui_currency",
})


@dataclass(frozen=True)
class AssetSpec:
    key: str
    label: str
    category: str
    size: tuple[int, int]
    prompt: str                       # {visual} {name} {style} {genre} {variant} {kind}
    placeholder: str = "figure"       # figure|scene|emblem|pixel|card|logo|button|hud
    variants: tuple[str, ...] = ()    # 고정 변형 (비어있으면 단일 이미지)
    variant_pool: tuple[str, ...] = ()  # 가변 변형 풀 (개수 선택형; 설정 시 이게 우선)
    entities: frozenset = ALL_ENTITIES
    default: bool = False
    is_image: bool = True             # False = 합성 산출물(sheet/video)
    desc: str = ""

    @property
    def variable(self) -> bool:
        """개수 선택형(3/5/7/10) 변형 에셋인지."""
        return bool(self.variant_pool)

    @property
    def character_ref(self) -> bool:
        """동일 캐릭터로 보여야 해서 앵커 레퍼런스를 쓰는 에셋인지."""
        return self.key in _CHAR_REF_KEYS

    @property
    def cutout(self) -> bool:
        """배경 제거(투명 알파) 대상 컷아웃 에셋인지."""
        return self.key in _CUTOUT_KEYS

    def resolve_variants(self, count: int) -> tuple[str, ...]:
        """가변이면 풀에서 count 개, 아니면 고정 변형(없으면 단일)."""
        if self.variant_pool:
            n = max(1, min(count, len(self.variant_pool)))
            return self.variant_pool[:n]
        return self.variants or ("",)


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
        variant_pool=("기쁨", "분노", "슬픔", "놀람", "수줍음", "무표정",
                      "윙크", "미소", "당황", "결의"),
        desc="비주얼노벨·대화 시스템용 감정 표정 (개수 선택)",
    ),
    AssetSpec(
        "poses", "액션 포즈", "character", (768, 768),
        "full body action pose of {name} performing a {variant} motion, "
        "{visual}, {style}, dynamic, plain background",
        placeholder="figure",
        variant_pool=("공격", "방어", "승리", "대기", "피격", "스킬 시전",
                      "이동", "사망", "조롱", "경계"),
        desc="공격·방어·승리 등 모션 스틸 (개수 선택)",
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
    AssetSpec(
        "emote", "이모트 세트", "character", (512, 512),
        "chat emote sticker of {name} expressing {variant}, {visual}, "
        "cute expressive sticker, bold outline, {genre}, plain background",
        placeholder="emblem",
        variant_pool=("웃음", "윙크", "화남", "눈물", "하트", "물음표",
                      "박수", "졸림", "놀람", "화이팅"),
        desc="채팅·리액션 이모트 스티커 (개수 선택)",
    ),
    AssetSpec(
        "companion", "탈것 / 펫", "character", (768, 768),
        "the mount or companion pet of {name}, a {genre} creature matching "
        "{visual} theme, full body, dynamic, plain neutral background",
        placeholder="figure",
        desc="탈것·펫·소환수",
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
        variant_pool=("스킬 I", "스킬 II", "스킬 III", "궁극기", "패시브",
                      "버프", "디버프", "소환", "강타", "치유"),
        desc="스킬·이펙트 아이콘 (개수 선택)",
    ),
    AssetSpec(
        "rarity_frame", "등급 프레임", "item", (512, 512),
        "game item card of {name} with a {variant} rarity ornate frame border, "
        "{visual} theme, {genre}, glowing rarity effect, centered",
        placeholder="emblem",
        variants=("일반", "고급", "희귀", "영웅", "전설"),
        desc="아이템 등급별 프레임",
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
    AssetSpec(
        "skybox", "스카이박스", "environment", (1280, 640),
        "panoramic 360 skybox of {name}'s world sky, {genre} setting, "
        "{visual} palette, seamless horizon, clouds and atmosphere, no characters",
        placeholder="scene",
        desc="하늘·파노라마 배경",
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
    AssetSpec(
        "splash", "스플래시 아트", "ui", (1280, 720),
        "cinematic key splash art of {name}, {visual}, {style}, {genre}, "
        "dramatic hero shot, epic lighting, loading screen composition",
        placeholder="splash",
        desc="로딩·키 비주얼 아트",
    ),
    AssetSpec(
        "namecard", "프로필 카드", "ui", (1024, 576),
        "horizontal profile namecard of {name}, {visual}, {genre}, "
        "avatar with name plate and decorative border, game profile card",
        placeholder="namecard",
        desc="프로필·명함 카드",
    ),

    # ── 인게임 UI / HUD ───────────────────────────────────────────
    AssetSpec(
        "ui_buttons", "버튼 세트", "hud", (512, 256),
        "game UI button in {variant} state, {genre} interface, {visual} color theme, "
        "rounded ornate button, clean vector UI, plain background",
        placeholder="button",
        variant_pool=("기본", "호버", "눌림", "비활성", "확인", "취소", "강조", "잠금"),
        desc="상태별 버튼 (기본/호버/눌림 등, 개수 선택)",
    ),
    AssetSpec(
        "ui_icons", "기능 아이콘 세트", "hud", (512, 512),
        "game UI functional icon for {variant}, {genre} interface, {visual} theme, "
        "flat minimal icon, single glyph, plain background",
        placeholder="emblem",
        variant_pool=("인벤토리", "설정", "상점", "지도", "퀘스트", "가방",
                      "스킬", "친구", "우편", "랭킹"),
        desc="메뉴·기능 아이콘 (인벤토리/설정/상점 등, 개수 선택)",
    ),
    AssetSpec(
        "ui_currency", "재화 아이콘", "hud", (512, 512),
        "game currency/resource icon for {variant}, {genre} theme, {visual} palette, "
        "shiny detailed icon, centered, plain background",
        placeholder="emblem",
        variant_pool=("골드", "젬", "에너지", "티켓", "코인", "크리스탈"),
        desc="화폐·재화 아이콘 (개수 선택)",
    ),
    AssetSpec(
        "ui_panel", "창 / 패널 프레임", "hud", (1024, 768),
        "game UI window panel frame, {genre} interface, {visual} theme, "
        "ornate border, empty content area, inventory/dialog panel, plain background",
        placeholder="panel",
        desc="인벤토리·대화창 등 패널 프레임",
    ),
    AssetSpec(
        "ui_hud", "HUD 바 세트", "hud", (1024, 512),
        "game HUD elements set, {genre} interface, {visual} theme, health mana and "
        "experience bars, minimap frame, skill slots, clean UI, plain background",
        placeholder="hud",
        desc="체력·마나·경험치 바, 미니맵/스킬 슬롯",
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
        "genres": GENRES,
        "art_styles": ART_STYLES,
        "image_models": IMAGE_MODELS,
        "assets": [
            {
                "key": s.key,
                "label": s.label,
                "category": s.category,
                "variants": list(s.variants),
                "variable": s.variable,
                "pool_max": len(s.variant_pool),
                "fixed_count": len(s.variants),
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
