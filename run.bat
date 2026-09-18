@echo off
REM Local launcher (Windows). Double-click = web playground. Or from a terminal:
REM   run.bat            web playground -> http://127.0.0.1:8000 (opens browser)
REM   run.bat demo       trial\systemone_demo.py      (add --dry-run to print the request only)
REM   run.bat triage     samples\comment_triage        (add --fixture for offline replay)
REM   run.bat test       offline test suite
setlocal
cd /d "%~dp0"
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
if not exist .venv ( echo · creating .venv & %PY% -m venv .venv || goto :fail )
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || goto :fail
if not exist .env (
  set /p KEY=TYPESAFE_API_KEY ^(비워두면 MOCK 모드^): 
  echo TYPESAFE_API_KEY=%KEY%> .env
  echo · saved to .env ^(git-ignored^)
)
set "CMD=%~1"
if "%CMD%"=="" set "CMD=web"
if "%CMD%"=="web"    ( echo · http://127.0.0.1:8000  ^(close this window to stop^) & .venv\Scripts\python webapp\app.py --auto --open & goto :end )
if "%CMD%"=="demo"   ( .venv\Scripts\python trial\systemone_demo.py %2 %3 %4 & goto :end )
if "%CMD%"=="triage" ( .venv\Scripts\python samples\comment_triage\triage.py %2 %3 %4 & goto :end )
if "%CMD%"=="test"   ( .venv\Scripts\python -m pytest -q & goto :end )
echo unknown command: %CMD% ^(web ^| demo ^| triage ^| test^)
:fail
echo.
echo 실행에 실패했습니다. Python 3.10+ 가 설치되어 있고 PATH 에 있는지 확인하세요 ^(https://www.python.org/downloads/^).
:end
pause
