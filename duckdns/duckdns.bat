@echo off
REM ============================================================
REM  DuckDNS updater (Windows) — points your DuckDNS domain at
REM  this machine's current public IP. Run on a schedule.
REM
REM  Usage: set your DOMAIN and TOKEN below, then run duckdns.bat
REM  Schedule it every 5 minutes:
REM    schtasks /Create /TN "DuckDNS" /TR "C:\path\duckdns.bat" /SC MINUTE /MO 5 /F
REM
REM  NOTE: The panel server runs on Oracle Cloud (Linux), so you
REM  will normally use duckdns.sh there. This .bat is provided in
REM  case you host the panel on a Windows box instead.
REM ============================================================

set DOMAIN=YOURNAME
set TOKEN=your-duckdns-token

REM Let DuckDNS detect the IP automatically (blank ip= param).
curl -k -s "https://www.duckdns.org/update?domains=%DOMAIN%&token=%TOKEN%&ip=" > "%~dp0duckdns.log"
type "%~dp0duckdns.log"
echo.
REM DuckDNS returns "OK" on success, "KO" on failure.
