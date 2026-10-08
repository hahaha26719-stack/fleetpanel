@echo off
REM ===================================================================
REM  Set / unset the FleetPanel login app as the SHELL for the KIOSK
REM  user only (true kiosk: no Explorer, no taskbar, no desktop).
REM
REM  Run AS ADMINISTRATOR.
REM
REM  Usage:
REM    set-kiosk-shell.bat set   kiosk     -> make the launcher the kiosk shell
REM    set-kiosk-shell.bat unset kiosk     -> restore the normal desktop
REM
REM  SAFETY:
REM   * Only touches the named user's hive (HKU), NEVER machine-wide, so your
REM     admin account keeps the normal Windows desktop.
REM   * Keep a backup admin account and the Ctrl+Alt+Q escape hatch ready.
REM ===================================================================
setlocal

net session >nul 2>&1
if %errorLevel% neq 0 ( echo [ERROR] Run this as Administrator. & pause & exit /b 1 )

set "ACTION=%~1"
set "KUSER=%~2"
if "%ACTION%"=="" set "ACTION=help"
if "%KUSER%"=="" set "KUSER=kiosk"

if /i "%ACTION%"=="help" (
    echo Usage: set-kiosk-shell.bat set^|unset ^<kiosk-username^>
    echo   set-kiosk-shell.bat set kiosk
    echo   set-kiosk-shell.bat unset kiosk
    exit /b 0
)

REM --- get the kiosk user's SID (PowerShell, since wmic is removed on Win11) ---
set "SID="
for /f "usebackq delims=" %%A in (`powershell -NoProfile -Command "(New-Object System.Security.Principal.NTAccount('%KUSER%')).Translate([System.Security.Principal.SecurityIdentifier]).Value" 2^>nul`) do set "SID=%%A"
if "%SID%"=="" ( echo [ERROR] Could not find user '%KUSER%'. Create it first. & exit /b 1 )
echo User '%KUSER%' SID = %SID%

set "PYW=pythonw"
where pythonw >nul 2>&1 || set "PYW=python"
set "SHELLCMD=%PYW% C:\FleetAgent\launcher.py"

REM --- the user's hive: loaded live as HKU\<SID>, or load from NTUSER.DAT ---
set "HIVE=HKU\%SID%"
set "LOADED=0"
reg query "%HIVE%" >nul 2>&1
if %errorLevel% neq 0 goto loadhive
goto havehive

:loadhive
REM user not logged in -> load their NTUSER.DAT temporarily
set "PROFPATH="
for /f "tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\%SID%" /v ProfileImagePath 2^>nul ^| find "ProfileImagePath"') do set "PROFPATH=%%B"
if not defined PROFPATH ( echo [ERROR] Could not find profile path for %KUSER%. & exit /b 1 )
set "HIVE=HKU\FleetKiosk"
reg load "%HIVE%" "%PROFPATH%\NTUSER.DAT" >nul 2>&1
if errorlevel 1 ( echo [ERROR] Could not load the user's hive ^(are they logged in?^). & exit /b 1 )
set "LOADED=1"

:havehive
set "KEY=%HIVE%\Software\Microsoft\Windows NT\CurrentVersion\Winlogon"

if /i "%ACTION%"=="set" goto do_set
if /i "%ACTION%"=="unset" goto do_unset
echo [ERROR] Unknown action '%ACTION%'. Use set or unset.
goto cleanup

:do_set
reg add "%KEY%" /v Shell /t REG_SZ /d "%SHELLCMD%" /f >nul
echo [OK] Kiosk shell SET for %KUSER%: %SHELLCMD%
echo      On next logon, %KUSER% gets NO desktop/taskbar - only FleetPanel.
goto cleanup

:do_unset
reg add "%KEY%" /v Shell /t REG_SZ /d "explorer.exe" /f >nul
echo [OK] Normal desktop RESTORED for %KUSER%.
goto cleanup

:cleanup
if "%LOADED%"=="1" reg unload "%HIVE%" >nul 2>&1

echo.
echo Reminders:
echo  - Your ADMIN account is unaffected (still has the normal desktop).
echo  - Escape from kiosk anytime: Ctrl+Alt+Q (admin password) or
echo    Ctrl+Alt+Del -^> Switch user -^> your backup admin.
echo  - To undo: set-kiosk-shell.bat unset %KUSER%
endlocal
