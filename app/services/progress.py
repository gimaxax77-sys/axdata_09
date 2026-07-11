"""생성 진행률 + 취소 스토어 (스레드 안전, 인메모리).

프론트엔드가 요청에 `progress_id` 를 실어 보내면, 파이프라인이 단계마다
여기에 진행 상태를 기록한다. 프론트는 `/api/progress/{id}` 를 폴링해
실제 진행률을 표시하고, `/api/cancel/{id}` 로 취소를 요청할 수 있다.
"""
from __future__ import annotations

import threading

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_MAX = 200  # 오래된 항목 방지용 상한


class Cancelled(Exception):
    """사용자 취소 요청 시 파이프라인에서 발생."""


def start(pid: str, total: int, label: str = "") -> None:
    if not pid:
        return
    with _LOCK:
        # 상한 초과 시 완료/오래된 항목부터 정리
        if len(_JOBS) > _MAX:
            for k in [k for k, v in _JOBS.items() if v.get("done")][: _MAX // 2]:
                _JOBS.pop(k, None)
        _JOBS[pid] = {
            "total": max(1, total), "current": 0, "label": label,
            "done": False, "cancelled": False, "error": None,
        }


def step(pid: str, current: int, label: str = "") -> None:
    if not pid:
        return
    with _LOCK:
        job = _JOBS.get(pid)
        if job:
            job["current"] = current
            if label:
                job["label"] = label


def advance(pid: str, label: str = "") -> None:
    """현재 단계 +1."""
    if not pid:
        return
    with _LOCK:
        job = _JOBS.get(pid)
        if job:
            job["current"] = min(job["total"], job["current"] + 1)
            if label:
                job["label"] = label


def finish(pid: str, error: str | None = None) -> None:
    if not pid:
        return
    with _LOCK:
        job = _JOBS.get(pid)
        if job:
            job["done"] = True
            job["current"] = job["total"]
            job["error"] = error


def cancel(pid: str) -> bool:
    with _LOCK:
        job = _JOBS.get(pid)
        if job and not job["done"]:
            job["cancelled"] = True
            return True
    return False


def is_cancelled(pid: str) -> bool:
    if not pid:
        return False
    with _LOCK:
        job = _JOBS.get(pid)
        return bool(job and job["cancelled"])


def check(pid: str) -> None:
    """취소되었으면 Cancelled 예외 발생 (파이프라인 단계 사이 호출용)."""
    if is_cancelled(pid):
        raise Cancelled("사용자가 생성을 취소했습니다.")


def snapshot(pid: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(pid)
        return dict(job) if job else None
