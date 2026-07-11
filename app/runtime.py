"""런타임 설정 (사용자가 UI 에서 바꾸는 값)을 파일에 영속화.

get_settings() 가 .env 값을 읽은 뒤, 여기 저장된 override 를 덮어쓴다.
runtime_config.json 은 gitignore 되며 각 PC 로컬에만 존재한다.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

_FILE = Path(__file__).resolve().parent.parent / "runtime_config.json"
_lock = threading.Lock()


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(cfg: dict) -> None:
    _FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def get_output_dir() -> str | None:
    return _load().get("output_dir")


def set_output_dir(path: str) -> None:
    with _lock:
        cfg = _load()
        cfg["output_dir"] = path
        _save(cfg)
