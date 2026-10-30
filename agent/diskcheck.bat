@echo off
REM Shows what's using disk space + cleans safe temp/cache. Run as Administrator.
echo === Free space on C: ===
powershell -NoProfile -Command "Get-PSDrive C | Select-Object @{N='FreeGB';E={[math]::round($_.Free/1GB,1)}}, @{N='UsedGB';E={[math]::round($_.Used/1GB,1)}}"
echo.
echo === Biggest folders in the user profile ===
powershell -NoProfile -Command "Get-ChildItem $env:USERPROFILE -Directory -ErrorAction SilentlyContinue | ForEach-Object { $s=(Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; [PSCustomObject]@{Folder=$_.Name; MB=[math]::round($s/1MB)} } | Sort-Object MB -Descending | Select-Object -First 10 | Format-Table -Auto"
echo.
echo === FleetPanel browser cache sizes (safe to clear) ===
powershell -NoProfile -Command "if(Test-Path $env:LOCALAPPDATA\FleetBrowser){ (Get-ChildItem $env:LOCALAPPDATA\FleetBrowser -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum/1MB } else {'none'}"
pause
