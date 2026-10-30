@echo off
REM Frees disk space by clearing SAFE caches/temp. Run as Administrator.
REM Does NOT touch user documents or FleetPanel roaming files on the Pi.
setlocal

echo [1] Clearing Windows temp files...
del /q /f /s "%TEMP%\*" >nul 2>&1
del /q /f /s "C:\Windows\Temp\*" >nul 2>&1

echo [2] Clearing FleetPanel browser caches (re-downloaded as needed)...
if exist "%LOCALAPPDATA%\FleetBrowser" rmdir /s /q "%LOCALAPPDATA%\FleetBrowser" >nul 2>&1
if exist "%TEMP%\fleetbrowser_pages" rmdir /s /q "%TEMP%\fleetbrowser_pages" >nul 2>&1

echo [3] Clearing Windows Update leftovers (safe)...
net stop wuauserv >nul 2>&1
rmdir /s /q "C:\Windows\SoftwareDistribution\Download" >nul 2>&1
net start wuauserv >nul 2>&1

echo [4] Emptying Recycle Bin...
powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"

echo [5] Running Windows Disk Cleanup (system files)...
cleanmgr /sagerun:1 >nul 2>&1

echo.
echo Done. Checking free space:
powershell -NoProfile -Command "Get-PSDrive C | Select-Object @{N='FreeGB';E={[math]::round($_.Free/1GB,1)}}"
pause
endlocal
