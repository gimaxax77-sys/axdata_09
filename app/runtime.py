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


# ── 프리셋 (캐릭터 설정 저장/불러오기) ────────────────────────────
def get_presets() -> dict:
    return _load().get("presets", {})


def save_preset(name: str, config: dict) -> None:
    with _lock:
        cfg = _load()
        cfg.setdefault("presets", {})[name] = config
        _save(cfg)


def delete_preset(name: str) -> None:
    with _lock:
        cfg = _load()
        cfg.get("presets", {}).pop(name, None)
        _save(cfg)


# ── 예산 / 비용 상한 ──────────────────────────────────────────────
# confirm_threshold: 예상 비용이 이 값을 넘으면 생성 전 확인 팝업 (USD)
# per_run_limit: 1회 생성 상한 (USD, 0=무제한) — 초과 시 차단
# monthly_limit: 월 예산 (USD, 0=무제한) — 이번 달 누적+예상이 넘으면 차단
DEFAULT_BUDGET = {
    "confirm_threshold": 0.5,
    "per_run_limit": 0.0,
    "monthly_limit": 0.0,
}


def get_budget() -> dict:
    return {**DEFAULT_BUDGET, **_load().get("budget", {})}


def set_budget(limits: dict) -> dict:
    with _lock:
        cfg = _load()
        cur = {**DEFAULT_BUDGET, **cfg.get("budget", {})}
        for k in DEFAULT_BUDGET:
            v = (limits or {}).get(k)
            if v is not None:
                try:
                    cur[k] = max(0.0, float(v))
                except (TypeError, ValueError):
                    pass
        cfg["budget"] = cur
        _save(cfg)
        return cur


def get_month_spend(month: str) -> float:
    return float(_load().get("spend_ledger", {}).get(month, 0.0))


def add_spend(month: str, usd: float) -> float:
    """이번 달 누적 지출에 실제 발생 비용을 더한다 (데모=0 이면 무시)."""
    usd = max(0.0, float(usd or 0.0))
    if usd <= 0:
        return get_month_spend(month)
    with _lock:
        cfg = _load()
        led = cfg.setdefault("spend_ledger", {})
        led[month] = round(led.get(month, 0.0) + usd, 4)
        _save(cfg)
        return led[month]
