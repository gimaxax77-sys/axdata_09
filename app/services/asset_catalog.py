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


def subject_label(subject: str) -> str:
    """제작 대상 라벨(폴더 대분류 등에 사용)."""
    subj = _SUBJECT_BY_KEY.get(subject)
    return subj["label"] if subj else "캐릭터"

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
    "cute big head chibi 3D game render, glossy, vibrant colors",
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

# 종류 → 세부 종류(2단계 드롭다운). 종류를 고르면 이 목록이 아래에 나온다.
# 아이템·환경·UI 대상에서 공통으로 쓴다(종류 값이 서로 겹치지 않으므로 한 dict).
ITEM_SUBTYPES = {
    "무기": ["장검", "단검", "도끼", "창", "양손검", "대검", "둔기", "채찍", "낫",
            "방패", "완드", "지팡이", "마법구", "마법서", "브로치", "건틀렛",
            "권총", "장총", "장궁", "단궁", "석궁", "발리스타"],
    "방어구": ["투구", "흉갑", "갑옷", "건틀릿", "각반", "부츠", "방패", "로브",
             "망토", "견갑"],
    "악세사리": ["반지", "목걸이", "귀걸이", "팔찌", "브로치", "벨트", "부적",
              "문장", "훈장", "오브"],
    "소비": ["포션", "엘릭서", "물약", "스크롤", "폭탄", "수류탄", "음식", "씨앗"],
    "재료": ["광석", "원석", "보석", "가죽", "목재", "약초", "마정석", "뼈", "천",
            "금속 주괴"],
}
ENV_SUBTYPES = {
    "던전": ["지하 감옥", "보스방", "함정방", "보물방", "입구 홀"],
    "숲": ["고목 숲", "요정 숲", "죽은 숲", "대나무 숲"],
    "설원": ["빙하", "눈보라 평원", "얼음 동굴"],
    "화산": ["용암 지대", "분화구", "화산 동굴"],
    "동굴": ["수정 동굴", "용암 동굴", "지하 호수"],
    "사막": ["모래 언덕", "오아시스", "사막 유적"],
    "해안": ["백사장", "절벽", "항구"],
    "도시": ["중세 마을", "대도시", "슬럼가", "시장"],
    "폐허": ["무너진 성", "고대 유적", "버려진 마을"],
    "신전": ["고대 신전", "지하 성소", "제단"],
    "초원": ["평원", "언덕", "꽃밭"],
    "늪지": ["독 늪", "안개 늪", "맹그로브"],
    "하늘": ["구름 위", "부유섬", "천공 성"],
    "우주": ["성운", "우주 정거장", "소행성대"],
}
_UI_COMPONENTS = ["전체 킷", "버튼", "창/패널", "아이콘", "HUD", "로고", "타이틀"]
UI_SUBTYPES = {theme: list(_UI_COMPONENTS) for theme in TYPE_LISTS["ui_types"]}
VFX_SUBTYPES = {
    "화염": ["폭발", "화염구", "불기둥", "불길", "잿불"],
    "빙결": ["빙결 폭발", "고드름", "눈보라", "얼음 파편"],
    "전격": ["낙뢰", "스파크", "전기장", "감전"],
    "맹독": ["독구름", "독액", "부식", "역병"],
    "신성": ["신성 폭발", "빛기둥", "치유 광휘", "축복"],
    "암흑": ["암흑 폭발", "그림자", "저주", "심연"],
    "대지": ["바위 분출", "지진", "가시", "모래폭풍"],
    "질풍": ["회오리", "바람 칼날", "돌풍"],
    "참격": ["베기", "십자 참격", "연속 베기"],
    "폭발": ["폭발", "충격파", "파편", "연쇄 폭발"],
    "치유 오라": ["회복 광휘", "재생", "생명의 빛"],
    "보호막": ["방어막", "결계", "반사막"],
    "버프": ["강화 오라", "공격 강화", "속도 강화"],
    "소환": ["소환진", "정령 소환", "그림자 분신"],
}

# 대상 통합(종류 값이 유일하므로 병합). 프론트가 종류로 세부 목록을 찾는다.
SUBTYPES = {**ITEM_SUBTYPES, **ENV_SUBTYPES, **UI_SUBTYPES, **VFX_SUBTYPES}

# 등급 — 10단계(뒤로 갈수록 고등급). 선택한 등급마다 1장씩.
# 고등급일수록 외형·등급 프레임을 강하게 강조(꼭 지켜지도록 style 에 명시).
# item/vfx: 이미지 프롬프트에 주입되는 등급별 시각 스타일.
RARITIES = [
    {"key": "일반",
     "item": "COMMON grade — plain ordinary materials, muted dull colors, NO glow and NO frame",
     "vfx": "common tier — small modest effect, simple sparse particles, muted colors"},
    {"key": "고급",
     "item": "UNCOMMON grade — slightly refined materials, faint sheen, a thin subtle silver border frame",
     "vfx": "uncommon tier — slightly brighter effect, a few more particles, faint glow"},
    {"key": "희귀",
     "item": "RARE grade — polished with blue accents, a simple glowing blue rarity frame border",
     "vfx": "rare tier — bright blue-tinted energy, moderate swirling particles"},
    {"key": "영웅",
     "item": "EPIC grade — rich purple accents and engraving, an ornate glowing purple rarity frame, soft aura",
     "vfx": "epic tier — vivid purple energy, dynamic swirling particles, notable glow"},
    {"key": "전설",
     "item": "LEGENDARY grade — ornate golden details and embedded gemstones, a radiant glowing GOLDEN rarity frame",
     "vfx": "legendary tier — large radiant golden burst, spectacular energy"},
    {"key": "초월",
     "item": "TRANSCENDENT grade — prismatic divine energy, brilliant halo, a highly elaborate glowing rainbow frame",
     "vfx": "transcendent tier — prismatic divine explosion, screen-filling holy light"},
    {"key": "멸망",
     "item": "DOOM grade — dark corrupted crimson-and-black, ominous jagged black-red frame, menacing malevolent aura",
     "vfx": "doom tier — dark crimson-black destructive blast, ominous corrupted energy"},
    {"key": "태초",
     "item": "PRIMORDIAL grade — ancient glowing cosmic runes, a radiant runic frame, timeless overwhelming power",
     "vfx": "primordial tier — ancient cosmic runic energy, vast radiant power"},
    {"key": "무아",
     "item": "VOID grade — pure white-gold ethereal cosmic aura, a reality-warping ornate frame, otherworldly",
     "vfx": "void tier — reality-warping cosmic cataclysm, pure white-gold apocalyptic energy"},
    {"key": "극",
     "item": "ULTIMATE PINNACLE grade — the absolute highest tier, overwhelming radiant godlike aura, the MOST "
             "elaborate and grand ornate frame of all, blindingly magnificent",
     "vfx": "ultimate pinnacle tier — the absolute highest effect, overwhelming godlike energy filling everything"},
]
RARITY_KEYS = [r["key"] for r in RARITIES]
RARITY_STYLE = {r["key"]: r["item"] for r in RARITIES}       # 아이템용
VFX_RARITY_STYLE = {r["key"]: r["vfx"] for r in RARITIES}    # 특수효과용
# 등급별 색(프레임·배지 공용 단일 소스)
RARITY_COLORS = {
    "일반": "#969696", "고급": "#c8cdd2", "희귀": "#468cf0", "영웅": "#a550e6",
    "전설": "#f0be3c", "초월": "#50dcdc", "멸망": "#c82837", "태초": "#3cc8aa",
    "무아": "#f5f0d2", "극": "#ff5ad2",
}
# 등급이 변형 축이 되는 에셋 → 각자의 등급 스타일 맵
RARITY_ASSETS = {"item_art": RARITY_STYLE, "vfx_art": VFX_RARITY_STYLE}

ALL_ENTITIES = frozenset(ENTITY_TYPES)

# 동일 캐릭터로 보여야 하는 에셋(앵커 이미지를 레퍼런스로 사용)
_CHAR_REF_KEYS = frozenset({
    "portrait", "fullbody", "expressions", "poses", "turnaround", "multiview_3d",
    "pixel_sprite", "emote", "card_frame", "splash", "namecard",
    "anim_idle", "anim_walk", "anim_attack",
})
# 배경 제거(투명 알파) 대상 — 스프라이트/아이콘 컷아웃
_CUTOUT_KEYS = frozenset({
    "portrait", "fullbody", "expressions", "poses", "turnaround", "multiview_3d",
    "pixel_sprite", "emblem", "emote", "companion",
    "item_art",
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
        "multiview_3d", "3D변환용 4방향", "character", (768, 1024),
        "orthographic {variant} view of {name} standing straight in a neutral A-pose, "
        "{visual}, {style}, identical proportions and outfit in every view, "
        "the ENTIRE character from the very top of the head to the soles of the feet is "
        "fully visible inside the frame with clear empty margin above the head and below "
        "the feet, zoomed-out full-length shot, nothing cropped or cut off at any edge, "
        "centered, flat even lighting, plain solid background — clean reference sheet for "
        "image-to-3D reconstruction",
        placeholder="figure",
        variants=("정면(front)", "후면(back)", "좌측(left)", "우측(right)"),
        desc="이미지→3D 변환용 전·후·좌·우 4방향(앵커 일관성)",
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
        "one frame of a smooth side-scroller WALK CYCLE — {name} in a strict flat SIDE "
        "profile, facing right and walking to the right, {variant}, full body head-to-toe "
        "with feet on the ground baseline, EMPTY HANDS and absolutely NO weapon or held "
        "object, arms swinging naturally opposite to the legs, {visual}, {genre}, the EXACT "
        "same character, outfit and colors as the reference — ONLY the leg and arm positions "
        "change between frames, nothing else, orthographic side-view camera locked at "
        "identical scale and centered framing, no rotation, no turning, no 3/4 view, "
        "plain background",
        placeholder="figure",
        variant_pool=(
            "right leg planted forward, left leg extended back, both feet on the ground",
            "body lowered, left foot pushing off the ground behind",
            "left leg lifting and swinging forward, passing under the body",
            "left leg swinging past with the knee raised at mid-stride",
            "left leg reaching forward, foot about to land ahead",
            "left leg planted forward, right leg extended back, both feet on the ground",
            "body lowered, right foot pushing off the ground behind",
            "right leg lifting and swinging forward, passing under the body",
            "right leg swinging past with the knee raised at mid-stride",
            "right leg reaching forward, foot about to land ahead"),
        desc="걷기 사이클 프레임 시퀀스(최대 10) · 시트+GIF 자동",
    ),
    AssetSpec(
        "anim_attack", "공격 애니메이션", "animation", (512, 512),
        "one frame of a BARE-HANDED melee/energy attack — {name} in a strict flat SIDE "
        "profile, facing right, {variant}, full body with feet on the ground baseline, "
        "EMPTY HANDS with NO held weapon (strikes with fists and {genre} energy), {visual}, "
        "{genre}, the EXACT same character, outfit and colors as the reference — ONLY the "
        "body and arm pose changes between frames, orthographic side-view camera locked at "
        "identical scale and centered framing, no rotation, no 3/4 view, plain background",
        placeholder="figure",
        variant_pool=(
            "ready fighting stance with both fists raised",
            "pulling the striking fist back, winding up",
            "fist fully wound back, body coiled and leaning",
            "stepping forward, striking fist beginning to thrust",
            "striking fist thrusting forward at mid-strike",
            "punch fully extended, energy burst bursting at the fist",
            "striking fist starting to retract, follow-through",
            "returning to the ready fighting stance"),
        desc="공격 모션 프레임 시퀀스(최대 8) · 시트+GIF 자동",
    ),

    # ── 아이템 / 장비 ─────────────────────────────────────────────
    AssetSpec(
        "item_art", "아이템 일러스트", "item", (768, 768),
        "detailed game item icon of {name}, {visual}, {genre} style, single centered item "
        "on a plain neutral background, no text. Rarity — {variant}: the rarity tier MUST be "
        "unmistakably conveyed by the item's ornateness AND a matching rarity frame/border "
        "(higher rarity = far more elaborate and dramatic; keep this strong and consistent)",
        placeholder="emblem",
        desc="아이템 본체 일러스트 (선택한 등급별로 1장씩, 등급 프레임 강조)",
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
        "subtypes": SUBTYPES,
        "rarities": RARITY_KEYS,
        "rarity_colors": RARITY_COLORS,
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
