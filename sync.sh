#!/usr/bin/env bash
# 로컬-원격 동기화(클라우드/리눅스용): 원격 변경을 받고(리베이스) 로컬 커밋을 올림
cd "$(dirname "$0")" || exit 1
echo "[sync] 원격 변경 받는 중 (git pull --rebase --autostash)..."
if ! git pull --rebase --autostash; then
  echo "[!] 충돌 발생 - 자동 병합 실패. git status 확인 후 해결하고 다시 실행하세요."
  exit 1
fi
echo "[sync] 로컬 커밋 올리는 중 (git push)..."
git push
echo "[sync] 완료 - 로컬과 원격이 동일합니다."
