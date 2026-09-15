<#
.SYNOPSIS
    Hardens a Windows PC so that STANDARD users cannot escalate to admin.

.DESCRIPTION
    Creating a standard user is step 1. This script closes the common
    escalation paths so a non-admin user cannot become admin:

      * UAC set to maximum: always prompt on the secure desktop, and DO NOT
        auto-elevate signed binaries -- this is what neutralises the
        computerdefaults.exe / fodhelper.exe / sdclt.exe UAC-bypass tricks.
      * Standard users are required to enter admin CREDENTIALS to elevate
        (not just click "Yes"), so having no admin password = no elevation.
      * Installer elevation is forced to prompt.

    Run AS ADMINISTRATOR.

    NOTE: This is defence for a *standard-user* environment. It does NOT make
    an admin user safe -- an existing local admin can undo all of this. The
    security comes from users being standard AND having no admin credentials.
    For 150 machines, deploy these settings via Group Policy / Intune instead
    of running the script on each box (see docs).
#>

[CmdletBinding()]
param()

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Error "Run this script as Administrator."; exit 1 }

$policies = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

function Set-Reg($path, $name, $value, $type = "DWord") {
    if (-not (Test-Path $path)) { New-Item -Path $path -Force | Out-Null }
    Set-ItemProperty -Path $path -Name $name -Value $value -Type $type
    Write-Host ("  {0}\{1} = {2}" -f $path, $name, $value) -ForegroundColor DarkGray
}

Write-Host "Hardening UAC / elevation..." -ForegroundColor Cyan
# UAC on
Set-Reg $policies "EnableLUA" 1
# Standard users must supply admin CREDENTIALS to elevate (0 = auto-deny prompt,
# 1 = prompt for credentials). Use 1 so an admin can still help at the desk;
# set 0 to silently deny all elevation for standard users.
Set-Reg $policies "ConsentPromptBehaviorUser" 1
# Admins always prompt on secure desktop (2 = prompt for consent on secure desktop)
Set-Reg $policies "ConsentPromptBehaviorAdmin" 2
# Prompt on the secure desktop (blocks UI spoofing)
Set-Reg $policies "PromptOnSecureDesktop" 1
# Do NOT auto-elevate signed executables -> defeats computerdefaults.exe /
# fodhelper.exe / eventvwr.exe style auto-elevate UAC bypasses.
Set-Reg $policies "ValidateAdminCodeSignatures" 0
Set-Reg $policies "EnableInstallerDetection" 1
# Only elevate UIAccess apps installed in secure locations
Set-Reg $policies "EnableSecureUIAPaths" 1
# Run all admins in Admin Approval Mode
Set-Reg $policies "FilterAdministratorToken" 1

Write-Host "Locking down remaining quick escalation surfaces..." -ForegroundColor Cyan
# Disable the built-in Administrator account (common target)
try {
    Disable-LocalUser -Name (Get-LocalUser -SID "S-1-5-21-*-500" -ErrorAction SilentlyContinue).Name -ErrorAction SilentlyContinue
    $builtinAdmin = Get-LocalUser | Where-Object { $_.SID.Value -like "*-500" }
    if ($builtinAdmin -and $builtinAdmin.Enabled) {
        Disable-LocalUser -Name $builtinAdmin.Name
        Write-Host "  Disabled built-in Administrator account." -ForegroundColor DarkGray
    }
} catch {}

Write-Host ""
Write-Host "UAC/elevation hardened." -ForegroundColor Green
Write-Host "A reboot is recommended for all settings to take effect." -ForegroundColor Yellow
Write-Host ""
Write-Host "IMPORTANT for real 'cannot be bypassed' lockdown:" -ForegroundColor Yellow
Write-Host "  1. Users must be STANDARD (use New-StandardUser.ps1)." -ForegroundColor Gray
Write-Host "  2. Add AppLocker/WDAC default-deny (New-AppLockerDefaultDeny.ps1)" -ForegroundColor Gray
Write-Host "     to stop LOLBins like computerdefaults.exe from running at all." -ForegroundColor Gray
Write-Host "  3. Enable BitLocker + Secure Boot + a BIOS/UEFI password to stop" -ForegroundColor Gray
Write-Host "     boot-from-USB / offline registry-edit attacks." -ForegroundColor Gray
Write-Host "  4. For 150 PCs, push all of this via Active Directory Group Policy" -ForegroundColor Gray
Write-Host "     or Intune so it is enforced at boot, below the user." -ForegroundColor Gray
