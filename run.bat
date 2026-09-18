@echo off
REM Local launcher (Windows). Double-click = web playground. Or from a terminal:
REM   run.bat            web playground -> http://127.0.0.1:8000, opens the browser
REM   run.bat demo       trial\systemone_demo.py      -- add --dry-run to print the request only
REM   run.bat triage     samples\comment_triage        -- add --fixture for offline replay
REM   run.bat test       offline test suite
REM Deliberately ASCII-only and free of parenthesized blocks: cmd.exe reads batch files in
REM the legacy code page, and a stray ")" inside a block aborts with "unexpected at this time".
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

set "PY=python"
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"

if exist .venv goto :deps
echo [1/3] creating .venv
%PY% -m venv .venv
if errorlevel 1 goto :fail

:deps
echo [2/3] installing requirements
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

if exist .env goto :run
set /p KEY=TYPESAFE_API_KEY - leave empty for MOCK mode: 
echo TYPESAFE_API_KEY=%KEY%> .env
echo saved to .env - git-ignored, asked only once

:run
set "CMD=%~1"
if "%CMD%"=="" set "CMD=web"
if "%CMD%"=="web" goto :web
if "%CMD%"=="demo" goto :demo
if "%CMD%"=="triage" goto :triage
if "%CMD%"=="test" goto :test
echo unknown command: %CMD%  -- use web, demo, triage or test
goto :end

:web
echo [3/3] http://127.0.0.1:8000  -- close this window to stop
.venv\Scripts\python webapp\app.py --auto --open
goto :end

:demo
.venv\Scripts\python trial\systemone_demo.py %2 %3 %4
goto :end

:triage
.venv\Scripts\python samples\comment_triage\triage.py %2 %3 %4
goto :end

:test
.venv\Scripts\python -m pytest -q
goto :end

:fail
echo.
echo Failed. Make sure Python 3.10+ is installed and on PATH: https://www.python.org/downloads/

:end
pause
