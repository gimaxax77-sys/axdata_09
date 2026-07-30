@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM 로컬-원격 동기화: 원격 변경을 받고(리베이스) 로컬 커밋을 올림
echo [sync] 원격 변경 받는 중 (git pull --rebase --autostash)...
git pull --rebase --autostash
if errorlevel 1 (
  echo.
  echo [!] 충돌 발생 - 자동 병합 실패. git status 로 확인 후 해결하고 다시 실행하세요.
  pause
  exit /b 1
)
echo [sync] 로컬 커밋 올리는 중 (git push)...
git push
echo.
echo [sync] 완료 - 로컬과 원격이 동일합니다.
pause
