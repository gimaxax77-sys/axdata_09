@echo off
chcp 65001 >nul
REM ── AXData Studio 서버 본체 (start.bat 이 백그라운드로 호출) ──
REM 직접 실행하지 마세요. 로그는 server.log 에 기록됩니다.
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
python -m uvicorn app.main:app --app-dir "%~dp0." --host 0.0.0.0 --port 8000 > "%~dp0server.log" 2>&1
