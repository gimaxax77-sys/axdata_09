#!/bin/bash
set -euo pipefail

# Inject the ponytail (simplicity-first) ruleset as session context.
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ponytail(단순화 우선) 원칙이 이 저장소에 활성화되어 있습니다. 코드 작성 전 사다리로 점검하세요: (1) 존재할 필요가 있는가(YAGNI) (2) 표준 라이브러리로 되는가 (3) 플랫폼 기본 기능인가 (4) 한 줄로 되는가 (5) 작동하는 최소 구현. 요청하지 않은 추상화·의존성·보일러플레이트는 넣지 않습니다. 의도적으로 모서리를 자른 곳은 'ponytail:' 주석으로 한계와 업그레이드 경로를 표기합니다. 사용 가능한 명령: /ponytail /ponytail-review /ponytail-audit /ponytail-debt /ponytail-gain /ponytail-help."}}
JSON
