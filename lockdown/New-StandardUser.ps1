<#
.SYNOPSIS
    Creates a Windows STANDARD (non-administrative) local user account.

.DESCRIPTION
    A standard user is a member of the "Users" group ONLY. It cannot:
      - edit HKLM registry, the hosts file, or Program Files
      - install drivers or software system-wide
      - run elevated tools or use UAC-bypass LOLBins (computerdefaults.exe,
        fodhelper.exe, etc.) to gain admin -- there is nothing to elevate to
        without separate admin credentials.
    This is the foundation that makes every other policy actually "stick",
    because the user cannot undo machine-level settings.

    Run this script itself AS ADMINISTRATOR (right-click > Run as administrator,
    or from an elevated PowerShell).

.PARAMETER Username
    The account name to create.

.PARAMETER FullName
    Optional display name.

.EXAMPLE
    .\New-StandardUser.ps1 -Username alice -FullName "Alice Smith"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$Username,
    [string]$FullName = "",
    [switch]$NoExpiry
)

# --- must run elevated -------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "This script must be run as Administrator."
    exit 1
}

# --- prompt for a password securely (never hard-code) ------------------------
$Password = Read-Host -AsSecureString "Enter a password for '$Username'"

# --- create the account if it does not exist ---------------------------------
if (Get-LocalUser -Name $Username -ErrorAction SilentlyContinue) {
    Write-Host "User '$Username' already exists. Ensuring it is standard-only..." -ForegroundColor Yellow
} else {
    $params = @{
        Name                 = $Username
        Password             = $Password
        FullName             = $FullName
        Description          = "Managed standard user (no admin privileges)"
        PasswordNeverExpires  = [bool]$NoExpiry
        UserMayNotChangePassword = $false
    }
    New-LocalUser @params | Out-Null
    Write-Host "Created standard user '$Username'." -ForegroundColor Green
}

# --- ensure member of Users, and NOT of Administrators -----------------------
try { Add-LocalGroupMember -Group "Users" -Member $Username -ErrorAction SilentlyContinue } catch {}

# Remove from Administrators if it somehow got added.
$adminGroup = (Get-LocalGroup -SID "S-1-5-32-544").Name   # localized "Administrators"
$isInAdmins = Get-LocalGroupMember -Group $adminGroup -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*\$Username" -or $_.Name -eq $Username }
if ($isInAdmins) {
    Remove-LocalGroupMember -Group $adminGroup -Member $Username -ErrorAction SilentlyContinue
    Write-Host "Removed '$Username' from Administrators." -ForegroundColor Green
}

# --- report ------------------------------------------------------------------
Write-Host ""
Write-Host "Group membership for '$Username':" -ForegroundColor Cyan
Get-LocalGroup | ForEach-Object {
    $g = $_.Name
    $members = Get-LocalGroupMember -Group $g -ErrorAction SilentlyContinue
    if ($members | Where-Object { $_.Name -like "*\$Username" }) { "  - $g" }
}

Write-Host ""
Write-Host "Done. '$Username' is a STANDARD user with no administrative rights." -ForegroundColor Green
Write-Host "Next: run Harden-Machine.ps1 (as admin) to lock down the PC so this" -ForegroundColor Green
Write-Host "user cannot escalate, then apply your FleetPanel policies." -ForegroundColor Green
