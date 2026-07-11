@echo off
chcp 65001 >nul
REM ── AXData Studio 실행 (서버를 백그라운드로 띄우고 브라우저 자동 열림) ──
cd /d "%~dp0"

REM 프로젝트 폴더가 맞는지 확인
if not exist "%~dp0app\main.py" (
  echo [ERROR] app\main.py 를 찾을 수 없습니다.
  echo 이 bat 은 프로젝트 폴더 안에 있어야 합니다: %~dp0
  pause
  exit /b 1
)

REM 이미 실행 중이면 브라우저만 열고 종료 (중복 실행 방지)
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if not errorlevel 1 (
  echo 서버가 이미 실행 중입니다. 브라우저를 엽니다...
  start "" http://127.0.0.1:8000
  timeout /t 2 >nul
  exit /b 0
)

REM 서버를 백그라운드(창 없이)로 실행 — 로그는 server.log 에 기록
wscript.exe "%~dp0_hidden.vbs"

REM 서버 부팅을 잠깐 기다렸다가 브라우저 자동 접속
timeout /t 4 >nul
start "" http://127.0.0.1:8000

echo ==================================================
echo    AXData Studio 가 백그라운드에서 실행 중입니다.
echo    접속 : http://127.0.0.1:8000
echo    로그 : server.log  (문제가 있으면 이 파일을 확인)
echo    종료 : stop.bat 을 실행하세요
echo ==================================================
timeout /t 3 >nul
exit
