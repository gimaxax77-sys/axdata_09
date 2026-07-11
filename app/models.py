"""Pydantic 스키마 — API 요청/응답 및 내부 데이터 모델."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenBase(BaseModel):
    """단일/일괄 생성 공통 옵션."""

    entity_type: str = Field("character", description="character | monster | npc")
    genre: str = Field("fantasy", description="장르")
    art_style: str = Field("semi-realistic digital painting", description="아트 스타일")
    keywords: str = Field("", description="추가 키워드(쉼표)")
    assets: list[str] = Field(default_factory=list, description="생성할 에셋 키")
    image_scale: float = Field(1.0, ge=0.5, le=2.0, description="해상도 배율")
    variant_count: int = Field(5, ge=1, le=10, description="가변 변형 장수")
    consistency: bool = Field(True, description="캐릭터 일관성(레퍼런스)")
    transparent: bool = Field(False, description="투명 배경(알파)")
    sprite_sheet: bool = Field(False, description="스프라이트 시트 패킹")
    style_lock: bool = Field(False, description="스타일 락")
    image_model: str = Field("", description="이미지 모델 오버라이드")
    progress_id: str = Field("", description="진행률/취소 추적용 클라이언트 토큰(선택)")


class GenerationRequest(GenBase):
    """단일 생성 요청."""

    name: str = Field("", description="이름 (비우면 GPT가 지어줌)")
    role: str = Field("", description="직업/종족/유형")


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
    name_en: str = ""  # 영문/로마자 이름 (한글 메인 + 영어 서브)
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
    art_style: str = ""  # 사용자가 고른 아트 스타일 (이미지 프롬프트에 주입)
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
    request: GenerationRequest | None = None  # 히스토리에서 설정 복원용


class BatchRequest(GenBase):
    """일괄 생성(도감) 요청 — 여러 개체를 한 번에 생성."""

    entity_type: str = Field("monster", description="character | monster | npc")
    count: int = Field(3, ge=1, le=8, description="생성 개수 (1~8)")
    roles: list[str] = Field(default_factory=list, description="개체별 역할/종족 (선택)")
    names: list[str] = Field(default_factory=list, description="개체별 이름 (선택)")
    make_codex: bool = Field(True, description="도감 오버뷰 이미지 생성")


class RegenerateRequest(BaseModel):
    """기존 잡의 특정 이미지 에셋 하나만 다시 생성."""

    asset_key: str = Field(..., description="다시 생성할 에셋 키")
    image_scale: float = Field(1.0, ge=0.5, le=2.0)
    variant_count: int = Field(5, ge=1, le=10)
    transparent: bool = Field(False)
    style_lock: bool = Field(False)
    image_model: str = Field("")


class ImportRunRequest(BaseModel):
    """CSV/스프레드시트 분석 결과(개체 목록)를 일괄 생성."""

    rows: list[GenerationRequest] = Field(default_factory=list)
    progress_id: str = Field("", description="진행률/취소 토큰")


class RepackRequest(BaseModel):
    """여러 변형(variant) 중 선택한 것만 남기고 시트를 재패킹."""

    asset_key: str = Field(..., description="변형 에셋 키 (예: expressions)")
    keep: list[str] = Field(..., description="남길 변형 파일명 목록 (예: expressions_1.png)")


class EditRequest(BaseModel):
    """기존 잡의 이미지 파일 하나를 편집."""

    file: str = Field(..., description="잡 폴더 기준 파일명 (예: portrait.png)")
    crop: dict | None = Field(None, description="{l,t,r,b} 프랙션 0~1")
    bg: str | None = Field(None, description="'#RRGGBB' 또는 'transparent'")
    brightness: float = Field(1.0, ge=0.1, le=3.0)
    contrast: float = Field(1.0, ge=0.1, le=3.0)
    saturation: float = Field(1.0, ge=0.0, le=3.0)


class BatchResult(BaseModel):
    batch_id: str
    entity_type: str
    entries: list[GenerationResult] = Field(default_factory=list)
    codex: GeneratedAsset | None = None
    warnings: list[str] = Field(default_factory=list)
