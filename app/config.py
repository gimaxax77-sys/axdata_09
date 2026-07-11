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
    return Settings()
