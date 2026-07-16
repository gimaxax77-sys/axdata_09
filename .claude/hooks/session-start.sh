#!/bin/bash
set -euo pipefail

# 로컬↔원격(클라우드) 자동 동기화 — 매 세션 시작 시 원격 변경을 받고 로컬 커밋을 올림.
# 훅 stdout 은 아래 JSON 전용이라 git 출력은 모두 버린다. 실패해도 세션은 계속(|| true).
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true
{ git pull --ff-only --quiet && git push --quiet; } >/dev/null 2>&1 || true

# 브랜치/동기화 상태 한 줄 (아래 JSON 의 systemMessage 로 사용자에게 표시).
_repo=$(basename "$PWD")
_branch=$(git branch --show-current 2>/dev/null || echo '?')
_lr=$(git rev-list --left-right --count '@{u}...HEAD' 2>/dev/null || echo '')
_behind=$(printf '%s' "$_lr" | cut -f1); _ahead=$(printf '%s' "$_lr" | cut -f2)
[ -n "${_ahead:-}" ] || _ahead=0
[ -n "${_behind:-}" ] || _behind=0
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then _tree='변경있음'; else _tree='clean'; fi
_status="[$_repo] 브랜치=$_branch · 원격대비 ahead ${_ahead}/behind ${_behind} · 작업트리 ${_tree}"

# ponytail 규칙 + 브랜치 상태를 세션 컨텍스트/알림으로 주입.
cat <<JSON
{"systemMessage":"$_status","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ponytail(단순화 우선) 원칙이 이 저장소에 활성화되어 있습니다. 코드 작성 전 사다리로 점검하세요: (1) 존재할 필요가 있는가(YAGNI) (2) 표준 라이브러리로 되는가 (3) 플랫폼 기본 기능인가 (4) 한 줄로 되는가 (5) 작동하는 최소 구현. 요청하지 않은 추상화·의존성·보일러플레이트는 넣지 않습니다. 의도적으로 모서리를 자른 곳은 'ponytail:' 주석으로 한계와 업그레이드 경로를 표기합니다. 사용 가능한 명령: /ponytail /ponytail-review /ponytail-audit /ponytail-debt /ponytail-gain /ponytail-help."}}
JSON
