# Lockdown — enforcing policy at the Windows level

This is the "it simply won't let them" layer. It makes policies stick against a
**standard (non-admin) user** by enforcing at the Windows kernel + filesystem
level, not just as reversible per-user settings.

## The honest security model (read this)

Real, un-bypassable-by-a-standard-user lockdown = **four layers together**.
No single script does it; each closes a different escape route.

| # | Layer | Script | Closes which bypass |
|---|-------|--------|---------------------|
| 1 | **Standard user, no admin** | `New-StandardUser.ps1` | The root cause. No admin = no kernel driver, no HKLM edit, no elevation. |
| 2 | **UAC / elevation hardening** | `Harden-Machine.ps1` | The `computerdefaults.exe` / `fodhelper.exe` UAC-bypass LOLBins (no auto-elevate). |
| 3 | **WDAC default-deny (kernel)** | `New-WDACDefaultDeny.ps1` | Running ANY unlisted binary at all — LOLBins, cmd, powershell, regedit — enforced at every launch, from boot. |
| 4 | **Strict NTFS/registry ACLs** | `Set-StrictPermissions.ps1` | Editing the hosts file / agent / policy files directly. |

Plus, for the **offline / physical** path (boot another OS from USB and edit files),
which no software can stop:

| Layer | How | Set by |
|-------|-----|--------|
| **BitLocker** | Encrypt the disk | You (admin) — `manage-bde -on C:` |
| **Secure Boot** | Firmware refuses unsigned boot | BIOS setup |
| **BIOS/UEFI password + disable USB boot** | Blocks boot-media attacks | BIOS setup (by hand or vendor firmware mgmt) |

### What this can and cannot do — plainly

- ✅ A **standard user** cannot bypass layers 1–4. They can't run the escalation
  tools, can't edit the protected files, can't disable the kernel policy.
- ✅ With BitLocker + Secure Boot + BIOS password, the **offline** attack is closed too.
- ❌ **An administrator can always undo all of it.** That is by design and correct —
  it's what separates device management from ransomware. If you sign the WDAC
  policy, even removing *that* needs your signing key, but a determined admin with
  physical access is always the ultimate authority. This is true of Windows itself,
  Active Directory, and every MDM — not a limitation of this project.

## Recommended order

```powershell
# On each PC, as Administrator (or push via Group Policy / Intune for 150 PCs):

# 1. Create the managed standard user
.\New-StandardUser.ps1 -Username alice -FullName "Alice Smith"

# 2. Harden UAC / elevation
.\Harden-Machine.ps1

# 3. Build + deploy WDAC in AUDIT first, review for a week, then enforce
.\New-WDACDefaultDeny.ps1 -OutDir C:\WDAC -Audit
#    ...review Event Viewer > CodeIntegrity > Operational...
.\New-WDACDefaultDeny.ps1 -OutDir C:\WDAC        # enforce

# 4. Lock the sensitive files
.\Set-StrictPermissions.ps1 -AgentPath C:\FleetAgent

# 5. (You, at each machine / via firmware mgmt) BitLocker + Secure Boot + BIOS password
manage-bde -on C: -RecoveryPassword
```

## For 150 machines

Do **not** hand-run these on 150 PCs. Use **Active Directory Group Policy** or
**Intune** to push:
- WDAC policy (Device Guard > Deploy Windows Defender Application Control)
- UAC settings (Security Options)
- Standard-user membership
- BitLocker + Secure Boot baseline

That enforces everything **at boot, below the user session** — the genuine
"it simply won't let them" outcome — and centrally, which is what a 150-seat
fleet needs. FleetPanel (the web panel) then rides on top for the day-to-day
user/group/web/printing/Explorer policy management.
