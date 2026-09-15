@echo off
REM ===================================================================
REM  FleetPanel Agent installer (run on each Windows PC AS ADMIN)
REM
REM  What it does:
REM    1. Copies the agent to C:\FleetAgent
REM    2. Writes agent_config.json (server URL + enroll secret)
REM    3. Registers a scheduled task that runs the agent at every logon
REM       with highest privileges (SYSTEM) so policies apply per-user.
REM    4. Applies strict permissions so standard users can't modify it.
REM
REM  Usage:
REM    setup-agent.bat https://YOURNAME.duckdns.org  YOUR_ENROLL_SECRET
REM ===================================================================
setlocal EnableDelayedExpansion

REM --- must be admin ---
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Please run this as Administrator.
    pause & exit /b 1
)

set "SERVER=%~1"
set "SECRET=%~2"
if "%SERVER%"=="" (
    echo Usage: setup-agent.bat ^<server-url^> ^<enroll-secret^>
    echo Example: setup-agent.bat https://mypanel.duckdns.org s3cr3t
    exit /b 1
)

set "DEST=C:\FleetAgent"
echo [1/5] Creating %DEST% ...
if not exist "%DEST%" mkdir "%DEST%"

echo [2/5] Copying agent files ...
copy /Y "%~dp0agent\agent.py" "%DEST%\agent.py" >nul

echo [3/5] Writing config ...
> "%DEST%\agent_config.json" (
    echo {
    echo   "server": "%SERVER%",
    echo   "enroll_secret": "%SECRET%"
    echo }
)

echo [4/5] Registering logon task (runs as SYSTEM, highest privileges) ...
REM Requires Python installed, OR replace with the frozen FleetAgent.exe path.
set "PY=python"
where %PY% >nul 2>&1 || set "PY=py"
schtasks /Create /TN "FleetAgent" /RU "SYSTEM" /RL HIGHEST /SC ONLOGON /F ^
  /TR "\"%PY%\" \"%DEST%\agent.py\"" >nul
if %errorLevel% neq 0 ( echo [WARN] Task creation failed - is Python installed? )

REM Also push roaming data back at logoff.
schtasks /Create /TN "FleetAgent-Logoff" /RU "SYSTEM" /RL HIGHEST /SC ONEVENT /F ^
  /EC Security /MO "*[System[(EventID=4647)]]" ^
  /TR "\"%PY%\" \"%DEST%\agent.py\" --logoff" >nul 2>&1

echo [5/5] Locking down the agent folder (standard users: read/execute only) ...
icacls "%DEST%" /inheritance:r >nul
icacls "%DEST%" /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "Users:(OI)(CI)RX" >nul

echo.
echo ============================================================
echo  Agent installed. It will enroll this PC and apply policies
echo  at the next user logon. Server: %SERVER%
echo.
echo  For full lockdown, also run (as admin) the scripts in
echo  the lockdown\ folder:
echo    - New-StandardUser.ps1      (make users non-admin)
echo    - Harden-Machine.ps1        (UAC hardening)
echo    - New-WDACDefaultDeny.ps1   (kernel default-deny)
echo    - Set-StrictPermissions.ps1 (lock sensitive files)
echo    - Enable-Firmware-Encryption.ps1 (BitLocker/Secure Boot)
echo ============================================================
pause
endlocal
