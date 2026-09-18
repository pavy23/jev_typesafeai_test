@echo off
REM One-shot local launcher (Windows): double-click. Creates .venv, installs deps,
REM asks for the key once, starts the playground and opens the browser.
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
if not exist .venv ( echo · creating .venv & %PY% -m venv .venv )
.venv\Scripts\python -m pip install -q -r requirements.txt
if not exist .env (
  set /p KEY=TYPESAFE_API_KEY ^(비워두면 MOCK 모드^): 
  echo TYPESAFE_API_KEY=%KEY%> .env
  echo · saved to .env ^(git-ignored^)
)
echo · starting http://127.0.0.1:8000  (close this window to stop)
.venv\Scripts\python webapp\app.py --auto --open
pause
