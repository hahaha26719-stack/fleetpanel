#!/usr/bin/env bash
# ============================================================
#  DuckDNS updater (Linux / Oracle Cloud VM)
#  Keeps your DuckDNS domain pointed at this VM's public IP.
#  Install as a cron job or systemd timer (see docs/DEPLOY.md).
# ============================================================
set -euo pipefail

DOMAIN="${DUCKDNS_DOMAIN:-YOURNAME}"
TOKEN="${DUCKDNS_TOKEN:-your-duckdns-token}"
LOG="${DUCKDNS_LOG:-/var/log/duckdns.log}"

# ip= left blank => DuckDNS uses the request's source IP (the VM's public IP).
RESULT="$(curl -k -s "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=")"
echo "$(date -Is) ${RESULT}" >> "${LOG}"

if [ "${RESULT}" = "OK" ]; then
  exit 0
else
  echo "DuckDNS update failed: ${RESULT}" >&2
  exit 1
fi
