"""로깅 설정 — print() 대신 표준 logging 사용.

각 모듈은 `log = get_logger(__name__)` 로 로거를 얻는다. 콘솔 출력은
기본 INFO 레벨이며, `AXDATA_LOG_LEVEL` 환경변수로 조정할 수 있다
(예: DEBUG). 서버 기동 시 `setup_logging()` 을 한 번 호출한다.
"""
from __future__ import annotations

import logging
import os

_CONFIGURED = False


def setup_logging() -> None:
    """루트 로거를 한 번만 구성. 콘솔 핸들러 + 간결한 포맷."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.getenv("AXDATA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root = logging.getLogger("axdata")
    root.setLevel(level)
    # 중복 핸들러 방지(리로드 대비)
    if not root.handlers:
        root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """모듈용 로거. `axdata.<module>` 네임스페이스로 묶는다."""
    setup_logging()
    short = name.split(".")[-1]
    return logging.getLogger(f"axdata.{short}")
