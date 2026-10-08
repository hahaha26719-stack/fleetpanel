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

echo [2/5] Copying agent + kid app files ...
copy /Y "%~dp0agent\agent.py"       "%DEST%\agent.py" >nul
copy /Y "%~dp0agent\kidcommon.py"   "%DEST%\kidcommon.py" >nul
copy /Y "%~dp0agent\launcher.py"    "%DEST%\launcher.py" >nul
copy /Y "%~dp0agent\kidnotepad.py"  "%DEST%\kidnotepad.py" >nul
copy /Y "%~dp0agent\kidppt.py"      "%DEST%\kidppt.py" >nul
copy /Y "%~dp0agent\kidbrowser.py"  "%DEST%\kidbrowser.py" >nul

echo     Installing Python packages (pywebview for the browser, pillow for images) ...
python -m pip install --quiet pywebview pillow 2>nul || echo [WARN] pip install failed - the browser needs pywebview and pictures need pillow; install Python + 'pip install pywebview pillow'.

echo [3/5] Writing config ...
> "%DEST%\agent_config.json" (
    echo {
    echo   "server": "%SERVER%",
    echo   "enroll_secret": "%SECRET%"
    echo }
)

echo [4/5] Registering logon task (runs as the LOGGED-IN USER, works on battery) ...
REM Find pythonw.exe (no console window) so there's nothing for a kid to close.
set "PYW=pythonw"
where pythonw >nul 2>&1 || set "PYW=python"

REM IMPORTANT: the GUI (login app, launcher, browser) must run as the
REM INTERACTIVE LOGGED-IN USER, NOT SYSTEM. WebView2/browsers cannot run as
REM SYSTEM (error 0x80080005). All kid policy enforcement is IN-APP, so no
REM SYSTEM rights are needed. Principal = BUILTIN\Users + InteractiveToken.
REM Battery conditions are disabled so it also runs on laptops.
set "TASKXML=%DEST%\fleetagent_task.xml"
> "%TASKXML%" (
    echo ^<?xml version="1.0" encoding="UTF-16"?^>
    echo ^<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
    echo   ^<RegistrationInfo^>^<Description^>FleetPanel login app (runs as user)^</Description^>^</RegistrationInfo^>
    echo   ^<Triggers^>^<LogonTrigger^>^<Enabled^>true^</Enabled^>^</LogonTrigger^>^</Triggers^>
    echo   ^<Principals^>^<Principal id="Author"^>
    echo     ^<GroupId^>S-1-5-32-545^</GroupId^>
    echo     ^<RunLevel^>LeastPrivilege^</RunLevel^>
    echo   ^</Principal^>^</Principals^>
    echo   ^<Settings^>
    echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
    echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
    echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
    echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
    echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
    echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
    echo   ^</Settings^>
    echo   ^<Actions Context="Author"^>
    echo     ^<Exec^>^<Command^>%PYW%^</Command^>^<Arguments^>"%DEST%\launcher.py"^</Arguments^>^</Exec^>
    echo   ^</Actions^>
    echo ^</Task^>
)
schtasks /Create /TN "FleetAgent" /XML "%TASKXML%" /F >nul
if %errorLevel% neq 0 ( echo [WARN] Task creation failed - is Python installed and on PATH? )

echo [5/5] Setting folder permissions ...
REM Lock the CODE so standard users can't modify the agent/apps, BUT let users
REM WRITE their own data folders so sign-in sync + reboot-wipe work.
icacls "%DEST%" /inheritance:r >nul
icacls "%DEST%" /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" "Users:(OI)(CI)RX" >nul
if not exist "%DEST%\roaming"   mkdir "%DEST%\roaming"
if not exist "%DEST%\userfiles" mkdir "%DEST%\userfiles"
REM Give Users full control of just the data dirs (so they can be written + wiped).
icacls "%DEST%\roaming"   /grant:r "Users:(OI)(CI)F" >nul
icacls "%DEST%\userfiles" /grant:r "Users:(OI)(CI)F" >nul

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
