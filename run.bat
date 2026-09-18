@echo off
REM Local launcher (Windows). Double-click = web playground. Or from a terminal:
REM   run.bat            web playground -> http://127.0.0.1:8000 (opens browser)
REM   run.bat demo       trial\systemone_demo.py      (add --dry-run to print the request only)
REM   run.bat triage     samples\comment_triage        (add --fixture for offline replay)
REM   run.bat test       offline test suite
REM This file is ASCII-only on purpose: cmd.exe reads batch files in the legacy code page
REM (CP949 on Korean Windows), so any UTF-8 text here would print garbled.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
if not exist .venv ( echo [1/3] creating .venv & %PY% -m venv .venv || goto :fail )
echo [2/3] installing requirements
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || goto :fail
if not exist .env (
  set /p KEY=TYPESAFE_API_KEY (leave empty for MOCK mode): 
  echo TYPESAFE_API_KEY=%KEY%> .env
  echo saved to .env (git-ignored, asked only once)
)
set "CMD=%~1"
if "%CMD%"=="" set "CMD=web"
if "%CMD%"=="web"    ( echo [3/3] http://127.0.0.1:8000  -- close this window to stop & .venv\Scripts\python webapp\app.py --auto --open & goto :end )
if "%CMD%"=="demo"   ( .venv\Scripts\python trial\systemone_demo.py %2 %3 %4 & goto :end )
if "%CMD%"=="triage" ( .venv\Scripts\python samples\comment_triage\triage.py %2 %3 %4 & goto :end )
if "%CMD%"=="test"   ( .venv\Scripts\python -m pytest -q & goto :end )
echo unknown command: %CMD%  (web ^| demo ^| triage ^| test)
:fail
echo.
echo Failed. Make sure Python 3.10+ is installed and on PATH: https://www.python.org/downloads/
:end
pause
