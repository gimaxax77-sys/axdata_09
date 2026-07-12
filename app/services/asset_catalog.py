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

# 카테고리 (중분류 — 세부 그룹 라벨)
CATEGORIES = {
    "character": "캐릭터 아트",
    "animation": "애니메이션",
    "item": "아이템 / 장비",
    "environment": "환경 / 배경",
    "vfx": "특수효과 (VFX)",
    "ui": "UI / 브랜딩",
    "hud": "인게임 UI / HUD",
    "composite": "통합 산출물",
}

# 상위 메뉴 (대분류) — 카테고리(중분류)를 6개 메뉴로 묶는다. 선택 화면과
# 결과 산출물이 모두 이 순서·구성으로 정리된다.
SUPERGROUPS = [
    {"key": "character", "label": "캐릭터", "cats": ["character", "animation"]},
    {"key": "item", "label": "아이템", "cats": ["item"]},
    {"key": "environment", "label": "환경", "cats": ["environment"]},
    {"key": "vfx", "label": "특수효과", "cats": ["vfx"]},
    {"key": "ui", "label": "UI", "cats": ["ui", "hud"]},
    {"key": "set", "label": "세트", "cats": ["composite"]},
]
_SUPER_CATS = {sg["key"]: sg["cats"] for sg in SUPERGROUPS}

# 제작 대상 (최상위) — '무엇을 만들지'. 캐릭터만 캐릭터 기획(이름·스탯·성격)을
# 생성하고, 나머지(아이템·환경·특수효과·UI)는 사물/디자인 산출물만 만든다.
# supers: 이 대상에서 노출할 상위 메뉴 키. concept: 캐릭터형 기획 생성 여부.
# role_preset: 역할 드롭다운 소스(job=직업 목록 / item_types=아이템 종류 / 없음=자유입력만)
# rarities: 등급 선택(체크박스) 노출 여부.
SUBJECTS = [
    {"key": "character", "label": "캐릭터", "concept": True, "supers": ["character", "set"],
     "role_preset": "job", "rarities": False},
    {"key": "item", "label": "아이템", "concept": False, "supers": ["item"],
     "role_preset": "item_types", "rarities": True},
    {"key": "environment", "label": "환경", "concept": False, "supers": ["environment"],
     "role_preset": "env_types", "rarities": False},
    {"key": "vfx", "label": "특수효과", "concept": False, "supers": ["vfx"],
     "role_preset": "vfx_types", "rarities": True},
    {"key": "ui", "label": "UI", "concept": False, "supers": ["ui"],
     "role_preset": "ui_types", "rarities": False},
]
_SUBJECT_BY_KEY = {s["key"]: s for s in SUBJECTS}


def subject_categories(subject: str) -> list[str]:
    """제작 대상에 노출할 카테고리(중분류) 목록."""
    subj = _SUBJECT_BY_KEY.get(subject)
    if not subj:
        return list(CATEGORIES)
    return [c for sg in subj["supers"] for c in _SUPER_CATS[sg]]

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

# 직업/역할 목록 (그룹별). 직접 입력도 가능.
ROLE_GROUPS = {
    "근접 전투": ["전사", "검사", "기사", "성기사", "검성", "광전사", "검투사",
                "무투가", "권법가", "격투가", "창기사", "창병", "사무라이", "검호"],
    "암살 / 은신": ["암살자", "도적", "닌자", "살수", "자객"],
    "원거리": ["궁수", "석궁병", "저격수", "총잡이", "거너", "포수"],
    "마법 / 주술": ["마법사", "대마법사", "흑마법사", "원소술사", "화염술사",
                  "빙결술사", "소환사", "강령술사", "주술사", "마도사", "정령술사"],
    "치유 / 지원": ["사제", "성직자", "힐러", "드루이드", "음유시인", "무희", "현자"],
    "탱커 / 방어": ["방패병", "수호기사", "가디언", "팔라딘"],
    "하이브리드": ["마검사", "룬나이트", "레인저", "사냥꾼", "비스트마스터", "광대"],
    "SF / 사이버펑크": ["해커", "넷러너", "파일럿", "사이보그", "안드로이드", "메카닉",
                     "엔지니어", "솔저", "스나이퍼", "테크노맨서", "바운티헌터"],
    "무협": ["검객", "도객", "권사", "창객", "암기술사", "의원", "독인",
            "사파 무인", "정파 무인"],
    "생활 / 기타": ["상인", "대장장이", "연금술사", "요리사", "모험가", "용병",
                  "기사단장", "군주"],
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

# 제작 대상별 '종류' 드롭다운 (장르 옆 선택박스 — 직업 드롭다운과 동일 위치).
# role 입력칸을 채우는 빠른 시작값이며, 자유 입력으로 더 구체화할 수 있다.
TYPE_LISTS = {
    "item_types": ["무기", "방어구", "악세사리", "소비", "재료"],
    "env_types": ["던전", "숲", "설원", "화산", "동굴", "사막", "해안", "도시",
                  "폐허", "신전", "초원", "늪지", "하늘", "우주"],
    "vfx_types": ["화염", "빙결", "전격", "맹독", "신성", "암흑", "대지", "질풍",
                  "참격", "폭발", "치유 오라", "보호막", "버프", "소환"],
    "ui_types": ["다크 판타지", "네온 사이버", "미니멀 플랫", "양피지 클래식",
                 "파스텔 카툰", "하이테크 SF", "고딕 호러", "픽셀 레트로"],
}
ITEM_TYPES = TYPE_LISTS["item_types"]  # 하위호환

# 등급 — 선택한 등급마다 1장씩. style 은 이미지 프롬프트에 주입(아이템/VFX 각각).
RARITIES = [
    {"key": "일반", "item": "common grade, plain ordinary materials, muted colors, no glow",
     "vfx": "common tier, small modest effect, simple sparse particles, muted colors"},
    {"key": "레어", "item": "rare grade, polished materials, subtle blue glow",
     "vfx": "rare tier, brighter effect, blue-tinted energy, moderate particles"},
    {"key": "매직", "item": "magic grade, enchanted glowing runes, soft green-blue aura",
     "vfx": "magic tier, glowing enchanted effect, swirling green-blue energy"},
    {"key": "레전드", "item": "legendary grade, ornate golden details, radiant glow, embedded gemstones",
     "vfx": "legendary tier, large radiant spectacular effect, golden brilliant burst"},
    {"key": "초월", "item": "transcendent grade, prismatic divine energy, brilliant halo, highly elaborate",
     "vfx": "transcendent tier, prismatic divine explosion, screen-filling holy light"},
    {"key": "멸망", "item": "doom grade, dark corrupted crimson-and-black, ominous flames, menacing",
     "vfx": "doom tier, dark crimson-black destructive blast, ominous corrupted energy"},
    {"key": "무아", "item": "ultimate void grade, pure white-gold cosmic aura, reality-warping ethereal glow",
     "vfx": "ultimate void tier, reality-warping cosmic cataclysm, pure white-gold apocalyptic energy"},
]
RARITY_KEYS = [r["key"] for r in RARITIES]
RARITY_STYLE = {r["key"]: r["item"] for r in RARITIES}       # 아이템용
VFX_RARITY_STYLE = {r["key"]: r["vfx"] for r in RARITIES}    # 특수효과용
# 등급이 변형 축이 되는 에셋 → 각자의 등급 스타일 맵
RARITY_ASSETS = {"item_art": RARITY_STYLE, "vfx_art": VFX_RARITY_STYLE}

ALL_ENTITIES = frozenset(ENTITY_TYPES)

# 동일 캐릭터로 보여야 하는 에셋(앵커 이미지를 레퍼런스로 사용)
_CHAR_REF_KEYS = frozenset({
    "portrait", "fullbody", "expressions", "poses", "turnaround",
    "pixel_sprite", "emote", "card_frame", "splash", "namecard",
    "anim_idle", "anim_walk", "anim_attack",
})
# 배경 제거(투명 알파) 대상 — 스프라이트/아이콘 컷아웃
_CUTOUT_KEYS = frozenset({
    "portrait", "fullbody", "expressions", "poses", "turnaround",
    "pixel_sprite", "emblem", "emote", "companion",
    "item_art", "weapon_icons", "item_grid", "skill_icons", "rarity_frame",
    "ui_icons", "ui_currency",
    "anim_idle", "anim_walk", "anim_attack",
    "vfx_art", "vfx_element", "vfx_skill", "vfx_hit",
})
# 애니메이션 프레임 시퀀스 에셋 (스프라이트 시트 + GIF 자동 생성)
_ANIM_KEYS = frozenset({"anim_idle", "anim_walk", "anim_attack"})


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

    @property
    def is_anim(self) -> bool:
        """프레임 시퀀스 애니메이션 에셋인지(시트+GIF 자동)."""
        return self.key in _ANIM_KEYS

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

    # ── 애니메이션 (프레임 시퀀스 → 시트 + GIF) ──────────────────
    AssetSpec(
        "anim_idle", "대기 애니메이션", "animation", (512, 512),
        "2D game side-view animation frame of {name}, idle pose — {variant}, "
        "full body, {visual}, {genre}, consistent character, plain background",
        placeholder="figure",
        variant_pool=("neutral standing", "breathing in slightly", "subtle shift",
                      "breathing out", "settle back", "small idle sway"),
        desc="대기(Idle) 프레임 시퀀스 · 시트+GIF 자동",
    ),
    AssetSpec(
        "anim_walk", "걷기 애니메이션", "animation", (512, 512),
        "2D game side-view walk-cycle frame of {name}, {variant}, full body, "
        "{visual}, {genre}, consistent character, side profile, plain background",
        placeholder="figure",
        variant_pool=("contact left foot forward", "recoil down", "passing pose",
                      "high point up", "contact right foot forward", "recoil down 2",
                      "passing pose 2", "high point up 2"),
        desc="걷기 사이클 프레임 시퀀스 · 시트+GIF 자동",
    ),
    AssetSpec(
        "anim_attack", "공격 애니메이션", "animation", (512, 512),
        "2D game side-view attack animation frame of {name}, {variant}, full body, "
        "{visual}, {genre}, dynamic action, consistent character, plain background",
        placeholder="figure",
        variant_pool=("ready stance", "wind-up back", "step forward start",
                      "full swing impact", "follow-through", "recovery to stance"),
        desc="공격 모션 프레임 시퀀스 · 시트+GIF 자동",
    ),

    # ── 아이템 / 장비 ─────────────────────────────────────────────
    AssetSpec(
        "item_art", "아이템 일러스트", "item", (768, 768),
        "detailed game item icon of {name}, {visual}, {genre} style, {variant} grade, "
        "single centered item on a plain neutral background, no text",
        placeholder="emblem",
        desc="아이템 본체 일러스트 (선택한 등급별로 1장씩)",
    ),
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
        "tileset", "타일셋 (이음새 없음)", "environment", (768, 768),
        "seamless repeating {genre} terrain texture for {name}'s environment, "
        "{visual} theme, top-down tileable ground texture, edges wrap perfectly, "
        "no visible border or seam, uniform, no characters",
        placeholder="scene",
        desc="이음새 없는 타일러블 텍스처 (3x3 미리보기 포함)",
    ),
    AssetSpec(
        "skybox", "스카이박스", "environment", (1280, 640),
        "panoramic 360 skybox of {name}'s world sky, {genre} setting, "
        "{visual} palette, seamless horizon, clouds and atmosphere, no characters",
        placeholder="scene",
        desc="하늘·파노라마 배경",
    ),

    # ── 특수효과 (VFX) ────────────────────────────────────────────
    AssetSpec(
        "vfx_art", "이펙트 (등급별)", "vfx", (768, 768),
        "dynamic game VFX special effect of {name}, {visual}, {genre} style, {variant}, "
        "glowing energy and particles, centered on a plain dark background, no text",
        placeholder="vfx",
        desc="이펙트 본체 — 선택한 등급마다 효과를 차등 생성",
    ),
    AssetSpec(
        "vfx_element", "속성 이펙트", "vfx", (512, 512),
        "game VFX effect sprite of a {variant} elemental magic burst, "
        "glowing energy particles, radiant {variant} attribute FX, {style}, "
        "isolated on a flat solid black background, no character, no text",
        placeholder="vfx",
        variant_pool=("화염", "빙결", "전격", "맹독", "신성", "암흑", "대지", "질풍",
                      "물", "용암"),
        desc="속성별(화염·빙결·전격…) 마법 이펙트 (개수 선택)",
    ),
    AssetSpec(
        "vfx_skill", "스킬 이펙트", "vfx", (512, 512),
        "game VFX effect sprite of a {variant} skill effect, dynamic energy, "
        "motion trails and sparks, {style}, isolated on a flat solid black "
        "background, no character, no text",
        placeholder="vfx",
        variant_pool=("참격", "폭발", "오라", "투사체", "치유", "보호막", "버프",
                      "디버프", "소환진", "회오리"),
        desc="스킬 연출(참격·폭발·오라·소환진…) 이펙트 (개수 선택)",
    ),
    AssetSpec(
        "vfx_hit", "타격/히트 이펙트", "vfx", (512, 512),
        "game VFX hit impact sprite of a {variant} impact effect, flash and "
        "debris particles, comic impact shape, {style}, isolated on a flat "
        "solid black background, no character, no text",
        placeholder="vfx",
        variant_pool=("강타", "관통", "폭산", "섬광", "베기", "감전", "빙결 히트",
                      "화염 히트"),
        desc="타격·피격 순간 이펙트 (개수 선택)",
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

    # ── 통합 산출물(세트) ─────────────────────────────────────────
    # 세트는 시트만 제공. 영상·BGM 은 세트 제작에서 제외한다.
    AssetSpec(
        "sheet", "캐릭터 시트 (PNG/PDF)", "composite", (0, 0), "",
        default=True, is_image=False,
        desc="아트 + 스탯 + 설정 통합 문서",
    ),
]

CATALOG: dict[str, AssetSpec] = {s.key: s for s in _SPECS}


def specs_for_entity(entity_type: str) -> list[AssetSpec]:
    return [s for s in _SPECS if entity_type in s.entities]


def default_keys(entity_type: str) -> list[str]:
    return [s.key for s in specs_for_entity(entity_type) if s.default]


def default_keys_for(subject: str, entity_type: str) -> list[str]:
    """제작 대상 범위 안에서의 기본 선택 에셋. 기본값이 없으면 첫 이미지 1종."""
    cats = set(subject_categories(subject))
    specs = [s for s in specs_for_entity(entity_type) if s.category in cats]
    picks = [s.key for s in specs if s.default]
    if picks:
        return picks
    img = next((s.key for s in specs if s.is_image), None)
    return [img] if img else [s.key for s in specs[:1]]


def catalog_payload() -> dict:
    """프론트엔드용 카탈로그 직렬화."""
    return {
        "entity_types": ENTITY_TYPES,
        "categories": CATEGORIES,
        "supergroups": SUPERGROUPS,
        "subjects": [
            {**s, "cats": subject_categories(s["key"]),
             "default_keys": default_keys_for(s["key"], "character")}
            for s in SUBJECTS
        ],
        "genres": GENRES,
        "art_styles": ART_STYLES,
        "role_groups": ROLE_GROUPS,
        "type_lists": TYPE_LISTS,
        "rarities": RARITY_KEYS,
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
                "size": list(s.size),
                "is_anim": s.is_anim,
                "cutout": s.cutout,
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
