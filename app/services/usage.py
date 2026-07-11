"""사용량·예상 비용 집계 (인메모리, 세션 단위).

⚠️ 각 제공자 API 는 '계정 잔액'을 조회하는 기능을 제공하지 않는다.
따라서 여기서는 이 앱이 실제로 호출한 만큼(토큰 수·이미지 장수)을 누적하고,
설정된 단가로 '예상 비용'을 계산해 보여준다. 실제 청구액/잔액은 각 콘솔에서
확인해야 한다.

서버가 재시작되면 0 으로 초기화된다.
"""
from __future__ import annotations

import threading

from ..config import Settings

_lock = threading.Lock()
_state = {
    "openai_input_tokens": 0,
    "openai_output_tokens": 0,
    "openai_calls": 0,
    "gemini_images": 0,
    "gemini_input_tokens": 0,
    "gemini_output_tokens": 0,
}


def record_openai(input_tokens: int, output_tokens: int) -> None:
    with _lock:
        _state["openai_input_tokens"] += int(input_tokens or 0)
        _state["openai_output_tokens"] += int(output_tokens or 0)
        _state["openai_calls"] += 1


def record_gemini_image(n: int = 1, input_tokens: int = 0, output_tokens: int = 0) -> None:
    with _lock:
        _state["gemini_images"] += int(n)
        _state["gemini_input_tokens"] += int(input_tokens or 0)
        _state["gemini_output_tokens"] += int(output_tokens or 0)


def reset() -> None:
    with _lock:
        for k in _state:
            _state[k] = 0


def snapshot(settings: Settings) -> dict:
    with _lock:
        s = dict(_state)

    gpt_cost = (
        s["openai_input_tokens"] / 1_000_000 * settings.openai_price_in
        + s["openai_output_tokens"] / 1_000_000 * settings.openai_price_out
    )
    # 이미지 비용: 장수 기반 기본 + (토큰 정보가 있으면) 출력 토큰 기반 정밀 추정 병기
    img_cost = s["gemini_images"] * settings.gemini_price_image
    g_out_tok = s["gemini_output_tokens"]
    g_in_tok = s["gemini_input_tokens"]
    total = gpt_cost + img_cost

    return {
        "openai": {
            "input_tokens": s["openai_input_tokens"],
            "output_tokens": s["openai_output_tokens"],
            "tokens": s["openai_input_tokens"] + s["openai_output_tokens"],
            "calls": s["openai_calls"],
            "cost_usd": round(gpt_cost, 4),
        },
        "gemini": {
            "images": s["gemini_images"],
            "input_tokens": g_in_tok,
            "output_tokens": g_out_tok,
            "cost_usd": round(img_cost, 4),
        },
        "total_usd": round(total, 4),
        "total_krw": round(total * settings.usd_krw),
        "note": "이 앱에서 생성한 사용량 기준 예상치입니다. 실제 잔액은 각 콘솔에서 확인하세요.",
    }
