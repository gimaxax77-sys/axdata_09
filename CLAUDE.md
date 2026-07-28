# 작업 규칙 — axdata_09

> **공통 규칙은 상위 `D:\.CODE\AXdata\CLAUDE.md` 한 곳에만 둡니다.**
> 소통 규칙 · 작업 방식 14원칙 · 답변·기록 규칙은 그 문서를 따르며, 여기서는 반복하지 않습니다.
> **호출 명령 `서브`(서브에이전트·승인 게이트 필수) · `롣/로드/ㄹㄷ`(클로드 직접) · `멤/mem`(기억 검색·기록)** 도 그 문서에 있습니다.
> (Claude Code는 하위 폴더에서 시작해도 상위 CLAUDE.md를 함께 읽습니다.)
> 이 문서에는 **이 프로젝트에서만 통하는 내용**만 적습니다.

## 이 프로젝트 전용 규칙

1. **테스트 명령**: `python -m pytest` (공통 규칙 7번의 이 프로젝트 명령 — 다른 프로젝트와 다릅니다).

## 프로젝트 개요

- **AXData Studio** — GPT(기획) + Gemini(아트, Nano Banana) + CapCut(영상)을 조합해 **캐릭터·몬스터·NPC** 게임 아트 에셋을 자동 제작하는 웹 툴. Python.
- 스택: **FastAPI + uvicorn** 백엔드, **바닐라 JS/HTML/CSS** 프론트(빌드 단계 없음), **Pillow** 이미지 처리.
- 실행: `start.bat`(Windows 원클릭) 또는 `uvicorn app.main:app --reload` → http://127.0.0.1:8000
- **데모 폴백**: API 키(`OPENAI_API_KEY`/`GEMINI_API_KEY`)가 없으면 로컬 플레이스홀더로 전 파이프라인이 끝까지 동작합니다.
- 결과물: `OUTPUT_DIR` 아래 `<엔티티>_<이름>_<날짜시각>/` 폴더로 자동 저장.
- 구조: `app/main.py`(FastAPI 라우트) · `app/services/`(오케스트레이션·서비스) · `app/static/`(웹 UI) · `tests/`(스모크 테스트).
- 아트 연결점(단일 진실 공급원): **`app/services/asset_catalog.py`** — 아트 요소를 여기 한 곳에서 정의하면 GPT 프롬프트·Gemini 생성·UI 체크리스트에 자동 반영됩니다.

## 코드 작성 원칙

- 아트 에셋은 **`asset_catalog.py` 한 곳에서만** 정의합니다(추가 시 전 계층 자동 반영).
- 모든 외부 호출(GPT/Gemini)은 **실패해도 데모 폴백으로 끝까지 동작**해야 합니다.
- 로깅은 `app/logging_config.py` 의 `get_logger` 를 씁니다(`print` 금지).
- 서비스는 역할별 모듈로 나눕니다(`pipeline`·`gpt_service`·`gemini_service`·`importer`·`editor`·`usage`·`progress` 등).
- 로컬 제어 엔드포인트(설정/폴더 열기/예산 등)는 `_require_local` 로 루프백만 허용합니다.
- 테스트: `python -m pytest` (스모크 테스트 `tests/test_smoke.py`).

## 현재 현황·백로그

- 상세 구현 현황·주요 API·남은 후보(백로그)는 **`research.md`** 참조.
  (CLAUDE.md는 매 세션 자동 로드되므로, 자주 바뀌는 상태·백로그는 여기 두지 않는다.)
