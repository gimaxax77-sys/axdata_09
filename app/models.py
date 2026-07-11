"""Pydantic 스키마 — API 요청/응답 및 내부 데이터 모델."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterRequest(BaseModel):
    """사용자 입력 — 캐릭터 생성 요청."""

    name: str = Field("", description="캐릭터 이름 (비우면 GPT가 지어줌)")
    genre: str = Field("fantasy", description="장르: fantasy, sci-fi, cyberpunk, ...")
    role: str = Field("", description="직업/역할: 전사, 마법사, 해커, ...")
    art_style: str = Field(
        "semi-realistic digital painting",
        description="아트 스타일 키워드",
    )
    keywords: str = Field("", description="추가 컨셉 키워드 (쉼표 구분)")

    # 어떤 산출물을 만들지
    make_sheet: bool = True
    make_assets: bool = True
    make_video: bool = True


class Stat(BaseModel):
    name: str
    value: int  # 0-100


class ImagePrompts(BaseModel):
    portrait: str
    fullbody: str
    icon: str


class CharacterConcept(BaseModel):
    """GPT가 생성하는 구조화된 캐릭터 기획서."""

    name: str
    title: str  # 이명/칭호
    genre: str
    role: str
    tagline: str  # 한 줄 소개
    appearance: str
    personality: str
    backstory: str
    abilities: list[str] = Field(default_factory=list)
    stats: list[Stat] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)  # hex codes
    image_prompts: ImagePrompts


class GeneratedAsset(BaseModel):
    kind: str  # portrait | fullbody | icon | sheet_png | sheet_pdf | video | capcut_draft
    path: str  # output 디렉토리 기준 상대 경로
    label: str
    demo: bool = False  # 데모(플레이스홀더) 여부


class GenerationResult(BaseModel):
    job_id: str
    concept: CharacterConcept
    assets: list[GeneratedAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
