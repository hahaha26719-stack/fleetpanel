@echo off
REM Shows every python/pythonw process, its CPU, and its command line, so we
REM can see exactly what is eating the CPU. Run as the kiosk user (or admin).
echo === Python processes + command lines ===
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | Select-Object ProcessId, Name, CommandLine | Format-List"
echo.
echo === Top CPU processes right now ===
powershell -NoProfile -Command "Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name, Id, CPU, @{N='Mem(MB)';E={[math]::round($_.WorkingSet/1MB)}} | Format-Table -Auto"
echo.
echo === How many python processes ===
powershell -NoProfile -Command "(Get-Process pythonw,python -ErrorAction SilentlyContinue).Count"
pause
