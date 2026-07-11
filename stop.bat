@echo off
chcp 65001 >nul
REM ── AXData Studio 종료 (8000 포트 서버 강제 종료) ──
echo AXData Studio 서버(포트 8000)를 종료합니다...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1
echo 완료. 이 창은 닫으셔도 됩니다.
pause
