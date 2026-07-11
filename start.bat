@echo off
REM ── AXData Studio 실행 (서버 시작 + 브라우저 자동 열림) ──
cd /d "%~dp0"
title AXData Studio Server

echo ==================================================
echo    AXData Studio  -  starting server...
echo ==================================================
echo.
echo    This PC :  http://127.0.0.1:8000
echo    Mobile  :  http://(아래 192.168.x.x 주소):8000
echo    --------------------------------------------
ipconfig | findstr /c:"IPv4"
echo    --------------------------------------------
echo    끄려면 이 창을 닫거나 Ctrl+C 를 누르세요.
echo.

REM 3초 뒤 기본 브라우저로 자동 접속 (서버 부팅 대기)
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000"

REM 서버 실행 (0.0.0.0 = 같은 와이파이의 폰에서도 접속 가능)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo 서버가 종료되었습니다.
pause
