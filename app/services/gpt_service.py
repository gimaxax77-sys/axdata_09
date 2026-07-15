"""GPT 서비스 — 캐릭터/몬스터/NPC 기획서 생성.

OpenAI Chat Completions 의 JSON 모드로 구조화된 컨셉을 만든다.
OPENAI_API_KEY 가 없으면 결정론적 로컬 생성기(데모 모드)로 폴백한다.
"""
from __future__ import annotations

import json
import random
import re

from ..config import Settings
from ..logging_config import get_logger
from ..models import EntityConcept, GenerationRequest, LabeledText, Stat

log = get_logger(__name__)

# 엔티티별 필드 의미(프롬프트 가이드)
_ENTITY_GUIDE = {
    "character": (
        "a PLAYABLE HERO character. role=class/job. personality=temperament. "
        "backstory=origin story. abilities=signature skills. "
        "extra should include 진영(faction), 무기(weapon), 목표(goal)."
    ),
    "monster": (
        "a MONSTER / enemy creature. role=species or creature type. "
        "personality=behavior pattern. backstory=habitat and lore. "
        "abilities=attack patterns. extra should include 위협도(threat level), "
        "서식지(habitat), 약점(weakness), 드랍 아이템(loot)."
    ),
    "npc": (
        "a NON-PLAYER CHARACTER (NPC). role=occupation. personality=disposition. "
        "backstory=background and role in the world. abilities=useful services/skills. "
        "extra should include 직업(occupation), 소속(affiliation), "
        "대표 대사(signature line), 제공 퀘스트(quest hook)."
    ),
}

SYSTEM_PROMPT = """\
You are a senior game designer and narrative writer.
Given a short brief, you invent a vivid, production-ready game entity.
The entity type is: {entity_kind}.
Guidance: {guidance}

IMPORTANT — Write ALL prose fields (name, title, tagline, appearance,
personality, backstory, abilities, extra label/value) in KOREAN (한국어).
The character MUST clearly match the given Role/Class exactly (e.g. 권사 =
bare-handed martial artist / fist fighter, NOT a swordsman). Honor the role.
Provide "name_en": an English or romanized version of the name.
Keep "visual_core" in ENGLISH — it is reused to build image-generation
prompts and must be a compact, concrete visual description (species,
silhouette, colors, materials, distinctive features), no camera or lighting.
The visual_core MUST reflect the exact role/class AND the GENRE's aesthetic
and attire. For example: wuxia = traditional East-Asian martial-arts robes /
hanbok-hanfu style flowing garments (NOT western plate armor); sci-fi =
futuristic high-tech suit; cyberpunk = neon augmented streetwear; steampunk =
Victorian brass-and-gear attire; fairytale = storybook costume. Describe the
outfit AND any weapon concretely so both clearly match the genre (e.g. wuxia
swords = slender jian or curved dao, NOT western broadswords; sci-fi = energy
weapons, NOT medieval swords).

Return ONLY a JSON object with EXACTLY these keys:
{{
  "name": string,                  // KOREAN
  "name_en": string,               // English / romanized
  "title": string,                 // KOREAN 이명/칭호
  "genre": string,
  "role": string,                  // KOREAN, must match the brief's role
  "tagline": string,               // KOREAN
  "appearance": string,            // KOREAN
  "personality": string,           // KOREAN
  "backstory": string,             // KOREAN
  "abilities": string[],           // KOREAN, 3-5 items
  "stats": [ {{"name": string, "value": integer 0-100}} ],  // exactly 6, KOREAN names
  "color_palette": string[],       // 4-5 hex colors
  "visual_core": string,           // ENGLISH visual description (match the role)
  "extra": [ {{"label": string, "value": string}} ]  // KOREAN, 3-4 facts
}}
"""


# 사물/디자인 대상(캐릭터 아님) — 캐릭터 기획 없이 간단한 묘사만 생성
_OBJECT_GUIDE = {
    "item": ("a single game ITEM / piece of equipment (weapon, armor, accessory, "
             "or consumable). title = 아이템 종류(예: 양손검, 판금 갑옷, 반지). "
             "appearance = 아이템의 생김새."),
    "environment": ("a game ENVIRONMENT / background location / scene. "
                    "title = 장소 유형(예: 폐허 도시, 고대 숲). appearance = 장면의 분위기."),
    "vfx": ("a game SPECIAL EFFECT (VFX) — a magic, skill, or impact effect. "
            "title = 이펙트 종류(예: 화염 폭발, 회복 오라). appearance = 이펙트의 모습."),
    "ui": ("a game UI / BRANDING design theme (interface, HUD, logo look). "
           "title = UI 스타일(예: 다크 판타지 UI). appearance = 인터페이스의 미감."),
}

OBJECT_SYSTEM_PROMPT = """\
You are a senior game art director.
Given a short brief, you design a game asset. The asset is: {subject_kind}.
Guidance: {guidance}

Write name/title/tagline/appearance in KOREAN (한국어). It MUST match the given
Type/Description exactly, and reflect the GENRE's aesthetic (wuxia = East-Asian
motifs; sci-fi = high-tech; cyberpunk = neon; steampunk = brass-and-gear; etc.).
Keep "visual_core" in ENGLISH — it is reused to build image-generation prompts and
must be a compact, concrete visual description (shapes, materials, colors, style),
no camera or lighting. Do NOT invent a character bio.
CRITICAL: the visual_core MUST precisely and unmistakably depict the EXACT type given
in the brief (e.g. if the type is a longsword, describe a longsword specifically — its
blade, hilt, guard — NOT a generic or different weapon). Keep the concept strong.

Return ONLY a JSON object with EXACTLY these keys:
{{
  "name": string,          // KOREAN 이름
  "name_en": string,       // English / romanized
  "title": string,         // KOREAN 종류/유형
  "tagline": string,       // KOREAN 한 줄 소개
  "appearance": string,    // KOREAN 생김새 묘사
  "visual_core": string,   // ENGLISH visual description
  "color_palette": string[]  // 4-5 hex colors
}}
"""


def generate_concept(req: GenerationRequest, settings: Settings) -> EntityConcept:
    subject = getattr(req, "subject", "character") or "character"
    # 사물/디자인 대상: 캐릭터 기획 없이 간단 묘사만
    if subject in _OBJECT_GUIDE:
        if settings.gpt_enabled:
            try:
                return _generate_object_with_openai(req, subject, settings)
            except Exception as exc:  # pragma: no cover - network/runtime guard
                log.warning("OpenAI 호출 실패, 데모 모드 폴백: %s", exc)
        return _generate_object_demo(req, subject)

    entity = req.entity_type if req.entity_type in _ENTITY_GUIDE else "character"
    if settings.gpt_enabled:
        try:
            return _generate_with_openai(req, entity, settings)
        except Exception as exc:  # pragma: no cover - network/runtime guard
            log.warning("OpenAI 호출 실패, 데모 모드 폴백: %s", exc)
    return _generate_demo(req, entity)


def _normalize_proportion(text: str) -> str:
    """'N등신'(한국식 몸 비율 표현)을 영어 비율 지시로 변환.

    이미지 모델이 '5등신'을 '머리 5개'로 오해해 그리는 문제를 막는다.
    항상 '머리 하나'임을 명시한다.
    """
    def repl(m):
        n = m.group(1)
        return (f"(body proportion about {n} heads tall, head-to-body height "
                f"ratio 1:{n}; ONE single character with exactly one head, "
                "no extra heads)")
    return re.sub(r"(\d+(?:\.\d+)?)\s*등신", repl, text or "")


def _build_user_brief(req: GenerationRequest) -> str:
    parts = [f"Entity type: {req.entity_type}"]
    if req.name:
        parts.append(f"Name: {req.name}")
    parts.append(f"Genre: {req.genre}")
    tg = getattr(req, "type_group", "")
    if tg and tg != req.role:
        parts.append(f"Category/Theme: {tg}")  # 종류/테마(예: 무기, 던전, 다크 판타지 UI)
    if req.role:
        parts.append(f"Role/Species/Type: {_normalize_proportion(req.role)}")
    parts.append(f"Art style: {req.art_style}")
    if req.keywords:
        parts.append(f"Extra keywords: {_normalize_proportion(req.keywords)}")
    return "\n".join(parts)


def _generate_with_openai(req, entity, settings) -> EntityConcept:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        temperature=0.9,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(
                entity_kind=entity, guidance=_ENTITY_GUIDE[entity])},
            {"role": "user", "content": _build_user_brief(req)},
        ],
    )
    # 사용량 기록 (예상 비용 표시용)
    try:
        from . import usage
        u = getattr(resp, "usage", None)
        if u is not None:
            usage.record_openai(getattr(u, "prompt_tokens", 0),
                                getattr(u, "completion_tokens", 0))
    except Exception as exc:
        log.debug("OpenAI 사용량 집계 실패(무시): %s", exc)

    data = json.loads(resp.choices[0].message.content)
    return _coerce_concept(data, req, entity)


def _coerce_concept(data, req, entity) -> EntityConcept:
    stats = [
        Stat(name=str(s.get("name", "?")), value=_clamp(s.get("value", 50)))
        for s in data.get("stats", [])
    ] or _default_stats(entity)

    extra = [
        LabeledText(label=str(e.get("label", "")), value=str(e.get("value", "")))
        for e in data.get("extra", []) if e.get("label")
    ]

    return EntityConcept(
        entity_type=entity,
        name=data.get("name") or req.name or _fallback_name(entity),
        name_en=data.get("name_en", ""),
        title=data.get("title", ""),
        genre=data.get("genre", req.genre),
        role=data.get("role", req.role),
        tagline=data.get("tagline", ""),
        appearance=data.get("appearance", ""),
        personality=data.get("personality", ""),
        backstory=data.get("backstory", ""),
        abilities=[str(a) for a in data.get("abilities", [])][:5],
        stats=stats[:6],
        color_palette=[str(c) for c in data.get("color_palette", [])][:5]
        or _palette_for(req.genre),
        visual_core=data.get("visual_core") or _demo_visual(req, entity),
        extra=extra[:4],
    )


def _generate_object_with_openai(req, subject, settings) -> EntityConcept:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        temperature=0.9,
        messages=[
            {"role": "system", "content": OBJECT_SYSTEM_PROMPT.format(
                subject_kind=subject, guidance=_OBJECT_GUIDE[subject])},
            {"role": "user", "content": _build_user_brief(req)},
        ],
    )
    try:
        from . import usage
        u = getattr(resp, "usage", None)
        if u is not None:
            usage.record_openai(getattr(u, "prompt_tokens", 0),
                                getattr(u, "completion_tokens", 0))
    except Exception as exc:
        log.debug("OpenAI 사용량 집계 실패(무시): %s", exc)

    data = json.loads(resp.choices[0].message.content)
    return _coerce_object(data, req, subject)


def _coerce_object(data, req, subject) -> EntityConcept:
    """사물/디자인 대상 — 캐릭터 기획 필드(스탯·성격·배경·능력)는 비운다."""
    return EntityConcept(
        entity_type=subject,
        name=data.get("name") or req.name or req.role or _OBJECT_BITS[subject]["names"][0],
        name_en=data.get("name_en", ""),
        title=data.get("title", "") or _OBJECT_BITS[subject]["title"],
        genre=data.get("genre", req.genre),
        role=req.role,
        tagline=data.get("tagline", ""),
        appearance=data.get("appearance", ""),
        color_palette=[str(c) for c in data.get("color_palette", [])][:5]
        or _palette_for(req.genre),
        visual_core=data.get("visual_core") or _object_visual(req, subject),
    )


def _clamp(v, lo: int = 5, hi: int = 100) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return 50


# ─────────────────────────────────────────────────────────────────────
# 데모 모드 (API 키 없이 동작)
# ─────────────────────────────────────────────────────────────────────
_GENRE_BITS = {
    "fantasy": {
        "character": {
            "titles": ["잿빛 검", "여명의 수호자", "폭풍의 방랑자", "은빛 서약자"],
            "roles": ["전사", "마법사", "성기사", "궁수", "도적"],
            "abilities": ["강타", "치유의 빛", "그림자 이동", "화염 폭발", "수호 결계"],
            "appearance": "낡은 판금 갑옷 위에 해진 망토를 두르고, 룬이 새겨진 검을 쥐고 있다.",
            "visual": "battle-worn plate armor, tattered cloak, rune-etched sword",
        },
        "monster": {
            "titles": ["심연의 포식자", "고대의 파수꾼", "저주받은 망령"],
            "roles": ["드래곤", "골렘", "언데드", "거대 늑대", "슬라임"],
            "abilities": ["화염 브레스", "대지 강타", "생명력 흡수", "독 안개", "광폭화"],
            "appearance": "비늘로 뒤덮인 거대한 몸체에서 검은 연기가 피어오르고, 붉은 눈이 번뜩인다.",
            "visual": "massive scaled body, black smoke, glowing red eyes, jagged spikes",
        },
        "npc": {
            "titles": ["떠돌이 상인", "마을의 현자", "비밀의 대장장이"],
            "roles": ["상인", "여관 주인", "대장장이", "사제", "정보상"],
            "abilities": ["장비 강화", "물약 판매", "정보 제공", "퀘스트 의뢰"],
            "appearance": "두툼한 로브에 여러 주머니를 두른 온화한 인상의 인물이 미소 짓고 있다.",
            "visual": "warm-faced merchant, thick robe, many pouches, friendly smile",
        },
    },
    "sci-fi": {
        "character": {
            "titles": ["궤도의 파수꾼", "제로 프로토콜", "성간 개척자"],
            "roles": ["파일럿", "엔지니어", "생체병기", "정찰병"],
            "abilities": ["플라즈마 사격", "은폐 필드", "나노 재생", "EMP 폭발"],
            "appearance": "매끈한 전투복에 홀로그램 바이저를 착용했고, 팔에 에너지 건틀릿이 빛난다.",
            "visual": "sleek combat suit, holographic visor, glowing energy gauntlet",
        },
        "monster": {
            "titles": ["변종 생체병기", "폭주 AI 드론", "외계 포식체"],
            "roles": ["뮤턴트", "전투 드론", "외계 생명체", "나노 군체"],
            "abilities": ["레이저 난사", "산성 분사", "자가 수복", "전자 교란"],
            "appearance": "금속과 유기체가 뒤섞인 몸체에서 푸른 전류가 스파크를 튀긴다.",
            "visual": "hybrid metal-organic body, blue electric sparks, chrome plating",
        },
        "npc": {
            "titles": ["정거장 관리자", "암시장 브로커", "AI 컴패니언"],
            "roles": ["기술자", "브로커", "의무관", "AI 비서"],
            "abilities": ["장비 업그레이드", "정보 거래", "치료", "항법 지원"],
            "appearance": "작업복 차림에 여러 툴을 두른 인물이 홀로 단말기를 조작하고 있다.",
            "visual": "utility jumpsuit, tool harness, holographic terminal",
        },
    },
    "cyberpunk": {
        "character": {
            "titles": ["네온의 유령", "코드 브레이커", "회로의 무법자"],
            "roles": ["해커", "청부업자", "사이보그", "정보상"],
            "abilities": ["시스템 해킹", "신경 과부하", "광학 위장", "과충전 대시"],
            "appearance": "네온 반사가 어린 가죽 재킷, 한쪽 눈에 사이버 임플란트가 빛난다.",
            "visual": "neon-lit leather jacket, cyber eye implant, data jacks on fingers",
        },
        "monster": {
            "titles": ["폭주 사이버독", "감시망 드론", "네트 유령"],
            "roles": ["보안 드론", "사이버 짐승", "전투 로봇", "바이러스 개체"],
            "abilities": ["기관총 난사", "추적 미사일", "해킹 방해", "자폭"],
            "appearance": "붉은 센서 눈을 번뜩이는 기계 몸체가 네온 불빛 아래 위협적으로 움직인다.",
            "visual": "chrome robotic body, red sensor eyes, exposed wiring, neon underglow",
        },
        "npc": {
            "titles": ["뒷골목 픽서", "임플란트 의사", "정보 딜러"],
            "roles": ["픽서", "리퍼독(의사)", "딜러", "바텐더"],
            "abilities": ["의뢰 중개", "사이버웨어 이식", "정보 판매", "은신처 제공"],
            "appearance": "네온 간판 아래 담배를 문 인물이 냉소적인 표정으로 기대 서 있다.",
            "visual": "cynical fixer under neon signs, augmented arm, worn trenchcoat",
        },
    },
}

_STAT_NAMES = {
    "character": ["체력", "공격력", "방어력", "민첩", "마력/기술", "행운"],
    "monster": ["체력", "공격력", "방어력", "속도", "위협도", "저항"],
    "npc": ["친밀도", "신뢰도", "재력", "정보력", "영향력", "행운"],
}

_FALLBACK_NAMES = {
    "character": ["카엘", "세라핀", "루멘", "녹스", "아리아", "제로"],
    "monster": ["그림", "발록", "누리스", "카론", "벨제", "라우"],
    "npc": ["바르트", "미라", "톰슨", "엘리사", "고든", "네리"],
}


def _fallback_name(entity: str) -> str:
    return random.choice(_FALLBACK_NAMES.get(entity, _FALLBACK_NAMES["character"]))


def _default_stats(entity: str) -> list[Stat]:
    names = _STAT_NAMES.get(entity, _STAT_NAMES["character"])
    return [Stat(name=n, value=random.randint(40, 92)) for n in names]


def _palette_for(genre: str) -> list[str]:
    palettes = {
        "fantasy": ["#2E1A47", "#6D466B", "#C89B3C", "#E6D5B8", "#8B2635"],
        "sci-fi": ["#0B132B", "#1C2541", "#3A506B", "#5BC0BE", "#E0FBFC"],
        "cyberpunk": ["#0D0221", "#FF2A6D", "#05D9E8", "#D1F7FF", "#7700A6"],
        "wuxia": ["#1A2A2E", "#3E5C57", "#8FB9A8", "#E8D8B0", "#A63A2E"],
        "steampunk": ["#2B1D12", "#6B4A2B", "#B8863B", "#D9C6A5", "#3A5A5C"],
        "fairytale": ["#3B2E5A", "#8C6BA6", "#F3A0C0", "#FCE6B8", "#7FB0A0"],
        "horror": ["#0A0A0C", "#26161A", "#5A1E24", "#8A8A8A", "#B03030"],
        "post-apoc": ["#241F1A", "#4A3F33", "#8A7A55", "#B5A688", "#7A4A3A"],
    }
    return palettes.get(genre.lower(), palettes["fantasy"])


def _bits(req, entity) -> dict:
    genre = req.genre.lower() if req.genre.lower() in _GENRE_BITS else "fantasy"
    return _GENRE_BITS[genre][entity]


def _demo_visual(req, entity) -> str:
    bits = _bits(req, entity)
    kw = f", {req.keywords}" if req.keywords else ""
    return f"{req.genre} {req.role or bits['roles'][0]}, {bits['visual']}{kw}"


# 사물/디자인 대상 데모 데이터 (API 키 없이 동작)
_OBJECT_BITS = {
    "item": {"title": "장비 아이템", "names": ["룬 브레이드", "비룡의 창", "성물 방패"],
             "visual": "ornate weapon or equipment, detailed materials, clean game item icon",
             "appearance": "정교한 세공이 돋보이는 장비로, 은은한 마력 광채가 흐른다."},
    "environment": {"title": "배경 장소", "names": ["잊혀진 성채", "안개 늪", "수정 동굴"],
                    "visual": "detailed environment concept scene, atmospheric background",
                    "appearance": "광활한 배경이 깊은 분위기를 자아낸다."},
    "vfx": {"title": "특수효과", "names": ["화염 폭발", "서리 파동", "신성 오라"],
            "visual": "dynamic particle effect, glowing energy burst, transparent background",
            "appearance": "강렬한 에너지가 사방으로 퍼지는 이펙트다."},
    "ui": {"title": "UI 테마", "names": ["다크 판타지 UI", "네온 HUD", "고전 양피지 UI"],
           "visual": "cohesive game UI kit, clean interface theme, consistent components",
           "appearance": "일관된 톤의 인터페이스 디자인이다."},
}


def _object_visual(req, subject) -> str:
    bits = _OBJECT_BITS[subject]
    kw = f", {req.keywords}" if req.keywords else ""
    desc = req.role or bits["names"][0]
    tg = getattr(req, "type_group", "")
    theme = f"{tg} " if tg and tg != req.role else ""
    return f"{req.genre} {theme}{desc}, {bits['visual']}{kw}"


def _generate_object_demo(req, subject) -> EntityConcept:
    bits = _OBJECT_BITS[subject]
    name = req.name or req.role or random.choice(bits["names"])
    return EntityConcept(
        entity_type=subject,
        name=name,
        title=bits["title"],
        genre=req.genre,
        role=req.role,
        tagline=f"{req.genre} 세계의 {req.role or bits['title']}.",
        appearance=bits["appearance"],
        color_palette=_palette_for(req.genre),
        visual_core=_object_visual(req, subject),
    )


def _demo_extra(entity: str, name: str, role: str, genre: str) -> list[LabeledText]:
    if entity == "monster":
        return [
            LabeledText(label="위협도", value=random.choice(["★★☆☆☆", "★★★☆☆", "★★★★☆", "★★★★★"])),
            LabeledText(label="서식지", value=f"{genre} 세계의 폐허와 던전 심층부"),
            LabeledText(label="약점", value=random.choice(["빛 속성", "화염", "머리 부위", "전기 충격"])),
            LabeledText(label="드랍 아이템", value=f"{name}의 정수, 희귀 소재"),
        ]
    if entity == "npc":
        return [
            LabeledText(label="직업", value=role),
            LabeledText(label="소속", value=f"{genre} 도시의 자유 상인 길드"),
            LabeledText(label="대표 대사", value="“좋은 물건이 들어왔지. 구경만 해도 좋아.”"),
            LabeledText(label="제공 퀘스트", value="잃어버린 화물 되찾기"),
        ]
    return [
        LabeledText(label="진영", value=random.choice(["자유 연합", "왕국 기사단", "그림자 결사"])),
        LabeledText(label="주무기", value=random.choice(["룬 검", "마법 지팡이", "쌍단검", "장궁"])),
        LabeledText(label="목표", value="잃어버린 과거를 되찾는 것"),
    ]


def _generate_demo(req, entity) -> EntityConcept:
    bits = _bits(req, entity)
    genre = req.genre
    name = req.name or _fallback_name(entity)
    role = req.role or random.choice(bits["roles"])
    title = random.choice(bits["titles"])

    noun = {"character": "영웅", "monster": "위협", "npc": "인물"}[entity]
    stories = {
        "character": (
            f"{name}은(는) 몰락한 가문의 마지막 후예로, 복수를 좇아 {role}의 길에 "
            "들어섰다. 여정 속에서 진짜 지켜야 할 것을 깨닫고, 지금은 이름을 감춘 채 "
            "세상을 떠돈다."
        ),
        "monster": (
            f"{name}은(는) 오래전 봉인되었던 존재로, 세계의 균열과 함께 다시 깨어났다. "
            f"{role}의 형상을 한 이 개체는 접근하는 모든 것을 위협으로 간주한다."
        ),
        "npc": (
            f"{name}은(는) 오랜 세월 이 지역을 지켜본 {role}(으)로, 수많은 모험가의 "
            "여정을 지켜봐 왔다. 세상 물정에 밝고, 도움을 주는 대가로 작은 부탁을 건넨다."
        ),
    }
    personality = {
        "character": "과묵하지만 동료에게는 끝까지 의리를 지킨다. 위기 앞에서 오히려 침착해진다.",
        "monster": "본능에 따라 영역을 침범한 자를 무자비하게 공격한다. 상처를 입으면 광폭화한다.",
        "npc": "붙임성 있고 능글맞다. 손해 보는 거래는 절대 하지 않는다.",
    }

    return EntityConcept(
        entity_type=entity,
        name=name,
        title=title,
        genre=genre,
        role=role,
        tagline=f"{title}, {name} — {genre} 세계의 {role} {noun}.",
        appearance=bits["appearance"],
        personality=personality[entity],
        backstory=stories[entity],
        abilities=random.sample(bits["abilities"], k=min(4, len(bits["abilities"]))),
        stats=_default_stats(entity),
        color_palette=_palette_for(genre),
        visual_core=_demo_visual(req, entity),
        extra=_demo_extra(entity, name, role, genre),
    )
