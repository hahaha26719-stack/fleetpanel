@echo off
REM ===================================================================
REM  FleetPanel — one-click UPDATE for a PC that already has the agent.
REM  Pulls the latest agent + kid app files from GitHub into C:\FleetAgent.
REM  No arguments needed. Run anytime there's an update.
REM
REM  (First-time install still uses setup-agent.bat with the server URL
REM   + enroll secret; this script just refreshes the code.)
REM ===================================================================
setlocal
set "DEST=C:\FleetAgent"
set "RAW=https://raw.githubusercontent.com/hahaha26719-stack/fleetpanel/main/agent"

if not exist "%DEST%" (
    echo [ERROR] %DEST% not found. Run setup-agent.bat first ^(first-time install^).
    pause & exit /b 1
)

echo Updating FleetPanel app files in %DEST% ...
for %%F in (agent kidcommon launcher kidnotepad kidppt kidbrowser) do (
    echo   - %%F.py
    curl -L -s -o "%DEST%\%%F.py" "%RAW%/%%F.py"
)

echo.
echo Done. Latest files pulled. If an app is open, close and reopen it.
echo (The browser engine/pillow are already installed by setup-agent.bat.)
pause
endlocal
