# research.md — 작업·조사 기록

> CLAUDE.md 규칙: 모든 질문·요구·요청과 진행 과정·결과를 신중·깊이·상세·명확·정확하게 정리해 여기에 누적 기록한다.

## 기록 형식
- **날짜 — 제목**
  - 요청:
  - 진행:
  - 결정·근거:
  - 결과:

---

## 2026-07-13 — CLAUDE.md 규칙 추가 및 전 저장소 횡전개
- 요청: CLAUDE.md에 "모든 답변을 신중·깊이·상세·명확·정확하게 정리하고 research.md에 기록" 규칙 추가, 전 저장소 기본 브랜치에 횡전개.
- 진행: 7개 저장소(axax77, axdata_01/03/05/07/09, gax)의 기본 브랜치 CLAUDE.md에 "답변·기록 규칙" 섹션 추가, 각 저장소에 research.md 생성.
- 결정·근거: '횡전개' = 새 세션이 실제로 여는 기본 브랜치에 반영(ponytail 배포와 동일 기준). 기존 CLAUDE.md는 보존하고 규칙 섹션만 추가(수술적 변경).
- 결과: 각 저장소 커밋·푸시 완료(아래 커밋 참조).

## 구현 현황·백로그 (CLAUDE.md에서 이전, 2026-07)
> CLAUDE.md 슬림화를 위해 자주 바뀌는 현황·백로그를 여기로 옮김.

### 현재 구현 현황
- 생성 모드 3종: 단일 생성 · 일괄(도감) · CSV/스프레드시트 가져오기(용도 기반 에셋 자동 설정).
- 아트 에셋 30+종: 초상화·전신·표정·포즈·도트·턴어라운드·엠블럼·이모트·탈것, 아이템/스킬 아이콘, 배경·타일셋·스카이박스, 특수효과(VFX), 로고·카드·배너·스플래시·프로필카드, 인게임 UI/HUD, 애니메이션·시트·영상·BGM. 변형 개수(3/5/7/10).
- 품질 옵션: 캐릭터 일관성(레퍼런스)·투명 배경(알파)·스프라이트 시트 패킹·스타일 락·이미지 모델 선택(Gemini/gpt-image-1).
- 결과 편집: 재생성(↻)·이미지 편집(✎)·변형 비교·채택 재패킹(⊞).
- 운영: 실시간 진행률+취소·예상 파일수/용량/비용·예산 경고(1회/월 상한)·사용량 집계·히스토리·프리셋·저장 경로. 폴더명 `장르_직업_캐릭명_날짜`.
- 경로 규칙: 상대경로는 as_posix()(슬래시)로 생성.
- 주요 API: /api/generate /api/generate_batch /api/import/{preview,run} /api/template.csv /api/regenerate /api/edit /api/repack /api/budget /api/progress /api/cancel.
- 테스트: tests/test_smoke.py.
- 개발 브랜치: claude/work-prep-status-check-axn3lj → main FF 병합.
- Windows 실행: start.bat/stop.bat/update.bat, 본체 _server.bat, 숨김 _hidden.vbs.

### 남은 후보(백로그)
- C. 실 API 실사용 점검 · D. 에셋별 프롬프트 고급 편집.
- 보류: run_pipeline 헬퍼 추출(P3-9) · imageio-ffmpeg extras 분리(P4-12).
