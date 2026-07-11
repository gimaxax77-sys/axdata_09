@echo off
chcp 65001 >nul
REM ── AXData Studio 실행 (서버 시작 + 브라우저 자동 열림) ──
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
title AXData Studio Server

echo ==================================================
echo    AXData Studio  -  starting server...
echo ==================================================
echo.
echo    This PC :  http://127.0.0.1:8000
echo    Mobile  :  use the 192.168.x.x address below
echo    --------------------------------------------
ipconfig | findstr /c:"IPv4"
echo    --------------------------------------------
echo    Stop: close this window or press Ctrl+C
echo.

REM 프로젝트 폴더가 맞는지 확인
if not exist "%~dp0app\main.py" (
  echo [ERROR] app\main.py 를 찾을 수 없습니다.
  echo 이 bat 은 프로젝트 폴더 안에 있어야 합니다: %~dp0
  pause
  exit /b 1
)

REM 3초 뒤 기본 브라우저로 자동 접속 (서버 부팅 대기)
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"

REM 서버 실행 (--app-dir 로 app 패키지 위치를 명시 → cwd 무관하게 동작)
REM 0.0.0.0 = 같은 와이파이의 폰에서도 접속 가능
python -m uvicorn app.main:app --app-dir "%~dp0." --host 0.0.0.0 --port 8000

echo.
echo 서버가 종료되었습니다.
pause
