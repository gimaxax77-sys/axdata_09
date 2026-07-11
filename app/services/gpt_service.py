"""GPT 서비스 — 캐릭터 기획서 생성.

OpenAI Chat Completions 의 JSON 모드로 구조화된 캐릭터 컨셉을 만든다.
OPENAI_API_KEY 가 없으면 결정론적 로컬 생성기(데모 모드)로 폴백한다.
"""
from __future__ import annotations

import json
import random

from ..config import Settings
from ..models import (
    CharacterConcept,
    CharacterRequest,
    ImagePrompts,
    Stat,
)

SYSTEM_PROMPT = """\
You are a senior game character designer and narrative writer.
Given a short brief, you invent a vivid, production-ready game character.
Always answer in the SAME language as the user's brief when writing prose
fields (appearance, personality, backstory, tagline, title). Keep
image_prompts in ENGLISH because they feed an image generation model.

Return ONLY a JSON object with EXACTLY these keys:
{
  "name": string,
  "title": string,          // epithet, e.g. "The Ashen Blade"
  "genre": string,
  "role": string,
  "tagline": string,        // one punchy line
  "appearance": string,     // 2-4 sentences, concrete visual detail
  "personality": string,    // 2-3 sentences
  "backstory": string,      // 3-5 sentences
  "abilities": string[],    // 3-5 signature abilities
  "stats": [ {"name": string, "value": integer 0-100}, ... ],  // 6 stats
  "color_palette": string[],  // 4-5 hex colors that define the character
  "image_prompts": {
     "portrait": string,    // detailed head-and-shoulders prompt
     "fullbody": string,    // full body / sprite prompt, clean background
     "icon": string         // simple emblem/item icon prompt
  }
}
Stats should include: 체력(HP), 공격력, 방어력, 민첩, 마력/기술, 행운
(or their genre-appropriate equivalents in the brief's language).
"""


def _build_user_brief(req: CharacterRequest) -> str:
    parts = []
    if req.name:
        parts.append(f"Name: {req.name}")
    parts.append(f"Genre: {req.genre}")
    if req.role:
        parts.append(f"Role/Class: {req.role}")
    parts.append(f"Art style: {req.art_style}")
    if req.keywords:
        parts.append(f"Extra keywords: {req.keywords}")
    return "\n".join(parts)


def generate_concept(req: CharacterRequest, settings: Settings) -> CharacterConcept:
    if settings.gpt_enabled:
        try:
            return _generate_with_openai(req, settings)
        except Exception as exc:  # pragma: no cover - network/runtime guard
            # 실패 시 데모 모드로 우아하게 폴백
            concept = _generate_demo(req)
            concept.tagline = f"{concept.tagline}"
            print(f"[gpt_service] OpenAI 호출 실패, 데모 모드 폴백: {exc}")
            return concept
    return _generate_demo(req)


def _generate_with_openai(req: CharacterRequest, settings: Settings) -> CharacterConcept:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        temperature=0.9,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_brief(req)},
        ],
    )
    data = json.loads(resp.choices[0].message.content)
    return _coerce_concept(data, req)


def _coerce_concept(data: dict, req: CharacterRequest) -> CharacterConcept:
    """LLM 응답을 스키마에 맞게 방어적으로 정규화."""
    stats = [
        Stat(name=str(s.get("name", "?")), value=_clamp(s.get("value", 50)))
        for s in data.get("stats", [])
    ] or _default_stats()

    ip = data.get("image_prompts", {}) or {}
    prompts = ImagePrompts(
        portrait=ip.get("portrait") or f"portrait of {data.get('name', 'a hero')}",
        fullbody=ip.get("fullbody") or f"full body of {data.get('name', 'a hero')}",
        icon=ip.get("icon") or "emblem icon",
    )

    return CharacterConcept(
        name=data.get("name") or req.name or "이름 없는 영웅",
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
        image_prompts=prompts,
    )


def _clamp(v, lo: int = 5, hi: int = 100) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return 50


# ── 데모 모드 (API 키 없이 동작) ─────────────────────────────────────

_GENRE_BITS = {
    "fantasy": {
        "titles": ["잿빛 검", "여명의 수호자", "폭풍의 방랑자", "은빛 서약자"],
        "roles": ["전사", "마법사", "성기사", "궁수", "도적"],
        "abilities": ["강타", "치유의 빛", "그림자 이동", "화염 폭발", "수호 결계"],
        "appearance": "낡은 판금 갑옷 위에 해진 망토를 두르고, 룬이 새겨진 검을 쥐고 있다.",
    },
    "sci-fi": {
        "titles": ["궤도의 파수꾼", "제로 프로토콜", "성간 개척자"],
        "roles": ["파일럿", "엔지니어", "생체병기", "정찰병"],
        "abilities": ["플라즈마 사격", "은폐 필드", "나노 재생", "EMP 폭발", "궤도 강하"],
        "appearance": "매끈한 전투복에 홀로그램 HUD 바이저를 착용했고, 팔에 에너지 건틀릿이 빛난다.",
    },
    "cyberpunk": {
        "titles": ["네온의 유령", "코드 브레이커", "회로의 무법자"],
        "roles": ["해커", "청부업자", "사이보그", "정보상"],
        "abilities": ["시스템 해킹", "신경 과부하", "광학 위장", "드론 소환", "과충전 대시"],
        "appearance": "네온 반사가 어린 가죽 재킷, 한쪽 눈에 사이버 임플란트, 손가락엔 데이터 잭이 달려 있다.",
    },
}

_DEFAULT_STAT_NAMES = ["체력", "공격력", "방어력", "민첩", "마력/기술", "행운"]


def _default_stats() -> list[Stat]:
    return [Stat(name=n, value=random.randint(45, 90)) for n in _DEFAULT_STAT_NAMES]


def _palette_for(genre: str) -> list[str]:
    palettes = {
        "fantasy": ["#2E1A47", "#6D466B", "#C89B3C", "#E6D5B8", "#8B2635"],
        "sci-fi": ["#0B132B", "#1C2541", "#3A506B", "#5BC0BE", "#E0FBFC"],
        "cyberpunk": ["#0D0221", "#FF2A6D", "#05D9E8", "#D1F7FF", "#7700A6"],
    }
    return palettes.get(genre.lower(), palettes["fantasy"])


def _generate_demo(req: CharacterRequest) -> CharacterConcept:
    genre = req.genre.lower() if req.genre.lower() in _GENRE_BITS else "fantasy"
    bits = _GENRE_BITS[genre]

    name = req.name or random.choice(
        ["카엘", "세라핀", "루멘", "녹스", "아리아", "제로", "바이런"]
    )
    role = req.role or random.choice(bits["roles"])
    title = random.choice(bits["titles"])
    kw = f" {req.keywords}" if req.keywords else ""

    prompts = ImagePrompts(
        portrait=(
            f"head and shoulders portrait of {name}, a {genre} {role}, "
            f"{req.art_style}, dramatic rim lighting, detailed face, "
            f"clean background{kw}"
        ),
        fullbody=(
            f"full body character sprite of {name}, a {genre} {role}, "
            f"{req.art_style}, dynamic hero pose, plain neutral background, "
            f"full figure visible{kw}"
        ),
        icon=(
            f"minimal emblem icon representing {name} the {role}, "
            f"{genre} game item icon, flat vector, centered, plain background{kw}"
        ),
    )

    return CharacterConcept(
        name=name,
        title=title,
        genre=req.genre,
        role=role,
        tagline=f"{title}, {name} — {genre} 세계를 가로지르는 {role}.",
        appearance=bits["appearance"],
        personality="과묵하지만 동료에게는 끝까지 의리를 지킨다. 위기 앞에서 오히려 침착해진다.",
        backstory=(
            f"{name}은(는) 몰락한 가문의 마지막 후예로, 어린 시절 모든 것을 잃었다. "
            f"복수를 좇아 {role}의 길에 들어섰지만, 여정 속에서 진짜 지켜야 할 것이 "
            "무엇인지 깨닫게 된다. 지금은 이름을 감춘 채 세상을 떠돈다."
        ),
        abilities=random.sample(bits["abilities"], k=min(4, len(bits["abilities"]))),
        stats=_default_stats(),
        color_palette=_palette_for(genre),
        image_prompts=prompts,
    )
