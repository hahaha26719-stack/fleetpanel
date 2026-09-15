# Windows Agent — build & deploy

The agent is a single Python file (`agent.py`). You can run it with Python on
each PC, or freeze it to a standalone `.exe` so target PCs need nothing installed.

## 1. Configure

Copy `agent_config.example.json` to `agent_config.json` and set your DuckDNS
server URL and (recommended) an enrollment secret that matches the server's
`FLEET_ENROLL_SECRET`.

## 2. Freeze to an .exe (recommended for 150 PCs)

On a Windows build machine with Python installed:

```bat
pip install pyinstaller
pyinstaller --onefile --name FleetAgent agent.py
```

The result is `dist\FleetAgent.exe`. Ship it alongside `agent_config.json`.

## 3. Run at logon (applies per-user roaming policies)

Register a scheduled task that runs at logon **with highest privileges** (needed
for HKLM registry edits and app-blocking):

```bat
schtasks /Create /TN "FleetAgent" /TR "\"C:\FleetAgent\FleetAgent.exe\"" ^
  /SC ONLOGON /RL HIGHEST /F
```

For the logoff data push, add a Group Policy logoff script or a second task that
runs `FleetAgent.exe --logoff`.

## Notes / limitations (read before trusting real data)

- Registry-based policies are the same mechanism Group Policy uses, but a local
  admin on the PC can reverse them. For true lockdown you still need Windows Pro
  policy enforcement or a domain.
- The app-block uses the Image File Execution Options "Debugger" trick — simple
  and effective for blocking known .exe names, but not a security boundary.
- Roaming sync here is **last-write-wins per file** and stores whole files. It's
  fine for documents/settings, not for large or concurrently-edited data.
- Always run the server over **HTTPS** (see `docs/DEPLOY.md`); the agent sends
  credentials and tokens over the wire.
