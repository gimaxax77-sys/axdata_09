"""Pydantic 스키마 — API 요청/응답 및 내부 데이터 모델."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    """사용자 입력 — 캐릭터/몬스터/NPC 생성 요청."""

    entity_type: str = Field("character", description="character | monster | npc")
    name: str = Field("", description="이름 (비우면 GPT가 지어줌)")
    genre: str = Field("fantasy", description="장르: fantasy, sci-fi, cyberpunk, ...")
    role: str = Field("", description="직업/종족/유형: 전사, 드래곤, 상인, ...")
    art_style: str = Field(
        "semi-realistic digital painting", description="아트 스타일 키워드"
    )
    keywords: str = Field("", description="추가 컨셉 키워드 (쉼표 구분)")

    # 생성할 에셋 키 목록 (asset_catalog 참조). 비우면 엔티티 기본값 사용.
    assets: list[str] = Field(default_factory=list)

    # 이미지 해상도 배율 (1.0=표준, 1.5=크게)
    image_scale: float = Field(1.0, ge=0.5, le=2.0)

    # 가변 변형 에셋(표정/포즈/스킬 등)의 생성 장수
    variant_count: int = Field(5, ge=1, le=10)


class Stat(BaseModel):
    name: str
    value: int  # 0-100


class LabeledText(BaseModel):
    """엔티티별 부가 정보 (예: 위협도/서식지, 직업/소속)."""

    label: str
    value: str


class EntityConcept(BaseModel):
    """GPT가 생성하는 구조화된 기획서 (캐릭터/몬스터/NPC 공통)."""

    entity_type: str = "character"
    name: str
    title: str  # 이명/칭호/종
    genre: str
    role: str  # 직업/종족/유형
    tagline: str  # 한 줄 소개
    appearance: str
    personality: str  # 몬스터=행동 양식, NPC=성향
    backstory: str  # 몬스터=서식지/전승, NPC=배경
    abilities: list[str] = Field(default_factory=list)  # 몬스터=공격 패턴
    stats: list[Stat] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)  # hex codes
    visual_core: str = ""  # 이미지 생성용 재사용 시각 묘사 (English)
    extra: list[LabeledText] = Field(default_factory=list)  # 엔티티별 부가 정보


class GeneratedAsset(BaseModel):
    kind: str  # 에셋 키 (portrait, expressions, ...) 또는 sheet_png/sheet_pdf/video
    category: str = "character"  # character|item|environment|ui|composite
    path: str  # output 디렉토리 기준 상대 경로
    label: str
    demo: bool = False  # 데모(플레이스홀더) 여부
    is_image: bool = True  # UI 렌더링 힌트


class GenerationResult(BaseModel):
    job_id: str
    concept: EntityConcept
    assets: list[GeneratedAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BatchRequest(BaseModel):
    """일괄 생성(도감) 요청 — 여러 개체를 한 번에 생성."""

    entity_type: str = Field("monster", description="character | monster | npc")
    genre: str = "fantasy"
    art_style: str = "semi-realistic digital painting"
    keywords: str = ""
    count: int = Field(3, ge=1, le=8, description="생성 개수 (1~8)")
    roles: list[str] = Field(default_factory=list, description="개체별 역할/종족 (선택)")
    names: list[str] = Field(default_factory=list, description="개체별 이름 (선택)")
    assets: list[str] = Field(default_factory=list, description="각 개체에 적용할 에셋")
    make_codex: bool = Field(True, description="도감 오버뷰 이미지 생성")
    image_scale: float = Field(1.0, ge=0.5, le=2.0)
    variant_count: int = Field(5, ge=1, le=10)


class BatchResult(BaseModel):
    batch_id: str
    entity_type: str
    entries: list[GenerationResult] = Field(default_factory=list)
    codex: GeneratedAsset | None = None
    warnings: list[str] = Field(default_factory=list)
