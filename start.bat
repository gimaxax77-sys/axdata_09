@echo off
chcp 65001 >nul
REM ── AXData Studio 실행 (서버를 백그라운드로 띄우고 준비되면 브라우저 열림) ──
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
echo AXData Studio 서버를 백그라운드로 시작합니다...
wscript.exe "%~dp0_hidden.vbs"

REM 서버가 완전히 준비될 때까지 대기(최대 40초) 후 브라우저 자동 접속
echo 서버 준비 중... (수초 걸릴 수 있습니다)
set /a _tries=0
:waitloop
timeout /t 1 >nul
netstat -ano | findstr :8000 | findstr LISTENING >nul 2>&1
if not errorlevel 1 goto :ready
set /a _tries+=1
if %_tries% lss 40 goto :waitloop
echo [경고] 서버가 아직 준비되지 않았습니다. server.log 를 확인하세요.
pause
exit /b 1

:ready
start "" http://127.0.0.1:8000
echo ==================================================
echo    AXData Studio 가 백그라운드에서 실행 중입니다.
echo    (이 창은 닫혀도 서버는 계속 실행됩니다)
echo    접속 : http://127.0.0.1:8000
echo    로그 : server.log
echo    종료 : stop.bat 을 실행하세요
echo ==================================================
timeout /t 3 >nul
exit
