#!/usr/bin/env python3
"""실 API 연동 스모크 테스트.

.env 의 OPENAI_API_KEY / GEMINI_API_KEY 로 각 제공자에 최소 호출을 보내
실제 연동이 되는지 확인한다.

사용법:
    python scripts/smoke_test.py          # 제공자별 최소 호출 점검
    python scripts/smoke_test.py --full   # 실제 캐릭터 1종 전체 생성까지

키가 없으면 해당 항목은 SKIP 으로 표시된다(데모 모드는 이 스크립트 없이도 동작).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# 프로젝트 루트를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402


GREEN, RED, YEL, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _ok(msg):
    print(f"  {GREEN}✔ PASS{RST} {msg}")


def _fail(msg):
    print(f"  {RED}✘ FAIL{RST} {msg}")


def _skip(msg):
    print(f"  {YEL}∘ SKIP{RST} {msg}")


def test_openai(settings) -> bool | None:
    print(f"\n[OpenAI GPT] 모델: {settings.openai_model}")
    if not settings.gpt_enabled:
        _skip("OPENAI_API_KEY 미설정 — .env 에 키를 넣으면 실제 호출을 검증합니다.")
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        t = time.time()
        resp = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Reply with a JSON object only."},
                {"role": "user", "content": 'Return {"ok": true, "hello": "world"}'},
            ],
        )
        dt = time.time() - t
        content = resp.choices[0].message.content
        _ok(f"응답 수신 ({dt:.1f}s): {content[:60]}")
        return True
    except Exception as exc:
        _fail(f"{type(exc).__name__}: {exc}")
        _hint_openai(exc)
        return False


def test_gemini(settings) -> bool | None:
    print(f"\n[Gemini 이미지] 모델: {settings.gemini_image_model}")
    if not settings.gemini_enabled:
        _skip("GEMINI_API_KEY 미설정 — .env 에 키를 넣으면 실제 호출을 검증합니다.")
        return None
    try:
        from app.services import gemini_service

        out = settings.output_path / "smoke" / "gemini_sample.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        t = time.time()
        ok = gemini_service._generate_with_gemini(
            "a simple test icon of a blue star, plain background",
            out, (512, 512), settings,
        )
        dt = time.time() - t
        if ok and out.exists():
            _ok(f"이미지 생성 ({dt:.1f}s) → {out}  ({out.stat().st_size // 1024} KB)")
            return True
        _fail("응답에 이미지 파트가 없습니다 (모델명/권한 확인 필요).")
        return False
    except BaseException as exc:  # noqa: BLE001 - pyo3 PanicException 은 Exception 이 아님
        _fail(f"{type(exc).__name__}: {str(exc)[:80]}")
        _hint_gemini(exc)
        return False


def test_full_pipeline(settings) -> None:
    print("\n[전체 파이프라인] 실제 API 로 캐릭터 1종 생성")
    from app.models import GenerationRequest
    from app.services import pipeline

    req = GenerationRequest(
        entity_type="character", genre="fantasy", role="마법사",
        assets=["portrait", "emblem", "sheet"],
    )
    t = time.time()
    res = pipeline.run_pipeline(req, settings, "smoke_full")
    dt = time.time() - t
    demo = any(a.demo for a in res.assets)
    print(f"  이름: {res.concept.name} · {res.concept.role}")
    print(f"  생성 {len(res.assets)}개 ({dt:.1f}s), 데모 폴백 포함: {demo}")
    for a in res.assets:
        tag = f"{YEL}DEMO{RST}" if a.demo else f"{GREEN}LIVE{RST}"
        print(f"    [{tag}] {a.label} → outputs/{a.path}")
    if demo:
        print(f"  {YEL}일부가 데모 폴백입니다 — 위 FAIL/힌트를 확인하세요.{RST}")
    else:
        _ok("모든 산출물이 실제 API 로 생성되었습니다.")


def _hint_openai(exc):
    s = str(exc).lower()
    if "auth" in s or "api key" in s or "401" in s:
        print(f"    {DIM}→ 키가 올바른지, 결제/크레딧이 활성인지 확인하세요.{RST}")
    elif "model" in s or "404" in s:
        print(f"    {DIM}→ OPENAI_MODEL 값을 확인하세요 (예: gpt-4o-mini, gpt-4o).{RST}")
    elif "rate" in s or "429" in s:
        print(f"    {DIM}→ 사용량 한도/속도 제한입니다. 잠시 후 재시도하세요.{RST}")


def _hint_gemini(exc):
    s = str(exc).lower()
    if ("_cffi_backend" in s or "cryptography" in s or "rust" in s
            or "import 실패" in s or "api call failed" in s or "panic" in s):
        print(f"    {DIM}→ google-genai/cryptography 설치가 깨졌거나 이 환경이 비정상입니다. "
              f"'pip install -U google-genai' 후 로컬/정상 환경에서 실행하세요.{RST}")
    elif "auth" in s or "api key" in s or "permission" in s or "401" in s or "403" in s:
        print(f"    {DIM}→ 키/권한을 확인하세요 (Google AI Studio 에서 발급).{RST}")
    elif "model" in s or "not found" in s or "404" in s:
        print(f"    {DIM}→ GEMINI_IMAGE_MODEL 을 확인하세요 (예: gemini-2.5-flash-image).{RST}")


def main() -> int:
    full = "--full" in sys.argv
    settings = get_settings()

    print("=" * 56)
    print(" AXData Studio — 실 API 연동 스모크 테스트")
    print("=" * 56)

    r1 = test_openai(settings)
    r2 = test_gemini(settings)
    if full and (settings.gpt_enabled or settings.gemini_enabled):
        test_full_pipeline(settings)

    print("\n" + "-" * 56)
    results = [("OpenAI", r1), ("Gemini", r2)]
    failed = [n for n, r in results if r is False]
    for name, r in results:
        state = "PASS" if r else ("SKIP" if r is None else "FAIL")
        print(f"  {name:8} {state}")
    print("-" * 56)

    if failed:
        print(f"{RED}실패: {', '.join(failed)} — 위 힌트를 확인하세요.{RST}")
        return 1
    if r1 is None and r2 is None:
        print(f"{YEL}키가 하나도 설정되지 않았습니다. .env 에 키를 넣고 다시 실행하세요.{RST}")
        return 2
    print(f"{GREEN}연동 정상 ✓{RST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
