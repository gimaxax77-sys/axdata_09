"""애플리케이션 설정.

환경변수 / .env 에서 값을 읽어옵니다. API 키가 없으면 각 서비스는
자동으로 로컬 "데모 모드"로 폴백하므로, 키 없이도 전체 파이프라인을
끝까지 실행해 볼 수 있습니다.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── AI providers ──────────────────────────────────────────────
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    gemini_api_key: str | None = None
    gemini_image_model: str = "gemini-2.5-flash-image"

    # ── Paths ─────────────────────────────────────────────────────
    output_dir: str = "outputs"
    capcut_draft_dir: str | None = None

    # ── Server ────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8000

    # ── 가격(예상 비용 추정용, 실제 청구액과 다를 수 있음) ─────────────
    # 단위: USD. 토큰 단가는 100만 토큰당 가격.
    openai_price_in: float = 0.15      # gpt-4o-mini 입력 기준(예시)
    openai_price_out: float = 0.60     # gpt-4o-mini 출력 기준(예시)
    gemini_price_image: float = 0.039  # 이미지 1장당(예시)
    usd_krw: float = 1350.0            # 원화 환산 환율(표시용)

    @property
    def output_path(self) -> Path:
        p = Path(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def gpt_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # 런타임 override (UI 에서 바꾼 저장 경로 등) 적용
    try:
        from .runtime import get_output_dir
        ov = get_output_dir()
        if ov:
            s.output_dir = ov
    except Exception:
        pass
    return s
