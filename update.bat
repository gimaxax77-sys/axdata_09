@echo off
chcp 65001 >nul
REM ── AXData Studio 업데이트 (종료 → git pull → 의존성 → 실행) ──
cd /d "%~dp0"
title AXData Studio Update

echo ==================================================
echo    AXData Studio  -  업데이트
echo ==================================================
echo.

REM 폴더 확인
if not exist "%~dp0app\main.py" (
  echo [ERROR] app\main.py 를 찾을 수 없습니다. 이 bat 은 프로젝트 폴더 안에 있어야 합니다.
  echo 폴더: %~dp0
  pause
  exit /b 1
)

echo [1/3] 실행 중인 서버 종료...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

echo [2/3] 최신 코드 받는 중 (git pull)...
git pull
if errorlevel 1 (
  echo.
  echo [ERROR] git pull 실패 — 인터넷 연결 또는 로컬 변경 충돌을 확인하세요.
  pause
  exit /b 1
)

echo [3/3] 의존성 갱신 (pip install)...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [경고] 일부 의존성 설치에 실패했을 수 있습니다. 위 메시지를 확인하세요.
)

echo.
echo ==================================================
echo    업데이트 완료!
echo ==================================================
echo.
choice /c YN /m "지금 앱을 실행할까요"
if errorlevel 2 goto :end
echo.
call "%~dp0start.bat"
goto :eof

:end
echo start.bat 을 더블클릭하면 언제든 실행할 수 있습니다.
pause
