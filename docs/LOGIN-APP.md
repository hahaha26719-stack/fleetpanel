# FleetPanel Login App — "log in with your account, not Microsoft"

This makes each managed Windows PC show a **full-screen FleetPanel login** at
startup. Users sign in with their **FleetPanel account** (created by the admin in
the web panel), their policies + roaming data load, and **Log out / Switch user**
returns to the login screen for the next person.

## How it works (the honest architecture)

Windows always needs *a* local Windows session to exist. So:

1. The PC **auto-logs-in** to ONE generic, locked-down Windows account
   (e.g. `kioskuser`, a **standard** — non-admin — account).
2. That account's startup program is **`login_app.py`** (the FleetPanel login).
   It runs full-screen, so the user only ever sees the FleetPanel login — not
   the Windows desktop.
3. The user's real identity = their **FleetPanel account**. Their policies and
   data follow them to any managed PC.

> This is interpretation **B**. It is NOT a Windows credential-provider
> replacement (that needs signed C++ and can lock you out). For 150 seats
> needing a *true* login-screen swap, Active Directory is the correct tool.
> This approach is safe, reversible, and works on the Banana Pi-hosted setup.

## Step 1 — create the generic kiosk Windows account (as admin)

Use the lockdown script you already have:

```powershell
lockdown\New-StandardUser.ps1 -Username kioskuser -FullName "Managed Kiosk"
```

Keep this account **standard (non-admin)** so users can't escape the app.

## Step 2 — install the agent + login app

```bat
setup-agent.bat https://YOUR-PANEL-URL  <enrollment_secret>
```

Then copy `login_app.py` next to `agent.py` in `C:\FleetAgent` (the installer
copies `agent.py`; add the login app too):

```bat
copy agent\login_app.py C:\FleetAgent\login_app.py
```

## Step 3 — auto-login the kiosk account

Set the generic account to sign in automatically. Easiest with Sysinternals
**Autologon** (recommended), or via registry:

```reg
Windows Registry Editor Version 5.00
[HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon]
"AutoAdminLogon"="1"
"DefaultUserName"="kioskuser"
"DefaultPassword"="<the kiosk account password>"
```

> The password sits in the registry in clear text with this method — which is
> exactly why the kiosk account must be **standard and heavily locked down**, and
> why real environments use AD/Autologon (encrypted). Treat the kiosk account as
> untrusted.

## Step 4 — launch the login app at logon (as that account's shell)

Two options:

**A) Startup shortcut (simple):** place a shortcut to
`pythonw.exe C:\FleetAgent\login_app.py` in
`C:\Users\kioskuser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`.

**B) Replace the shell (stronger kiosk):** set the login app as the account's
shell so no desktop/taskbar appears:

```reg
[HKEY_CURRENT_USER\Software\Microsoft\Windows NT\CurrentVersion\Winlogon]
"Shell"="pythonw.exe C:\\FleetAgent\\login_app.py"
```

Use `pythonw.exe` (no console window). If you froze it to `FleetAgent.exe`, point
to a `login_app.exe` build instead (see `agent/BUILD.md`).

## Step 5 — lock it down so users can't escape

Apply the lockdown scripts to the kiosk account/machine so users can't Alt-Tab
or task-switch out of the login app:

```powershell
lockdown\Harden-Machine.ps1
lockdown\New-WDACDefaultDeny.ps1 -OutDir C:\WDAC -Audit   # audit, then enforce
lockdown\Set-StrictPermissions.ps1 -AgentPath C:\FleetAgent
```

Also useful FleetPanel policies for kiosk accounts: `disable_task_manager`,
`disable_run`, `no_shutdown`, `hide_control_panel`, `disable_cmd`.

## Testing on a normal desktop (no kiosk)

```bash
python login_app.py --windowed
```

This opens a resizable window and lets you press **Escape** to quit — so you can
try the login → session → logout flow without full-screen locking you in.

## Login flow summary

```
Boot → auto-login kiosk account → login_app.py (full screen)
     → user enters FleetPanel username/password
     → agent pulls their roaming data + applies their policies
     → session screen ("Welcome, <name>")
     → "Log out / Switch user"
     → agent pushes data back + reverts per-user policies
     → back to the login screen for the next user
```
