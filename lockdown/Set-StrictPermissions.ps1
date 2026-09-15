<#
.SYNOPSIS
    Applies strict NTFS + registry permissions so standard users cannot modify
    the files/keys that policies live in.

.DESCRIPTION
    Even without WDAC, this makes tampering hard for a standard (non-admin)
    user by locking write access to the sensitive locations:

      * The hosts file (so web blocks can't be edited out)
      * The agent install folder (so the enforcement agent can't be replaced)
      * The WDAC policy folder

    Standard users keep READ + EXECUTE where needed, but lose WRITE/DELETE.
    An administrator (you) retains full control -- as it must be.

    NOTE: This only holds while the user is NON-ADMIN. An admin can always
    re-take ownership. Pair with New-StandardUser.ps1 + WDAC + BitLocker.

    Run AS ADMINISTRATOR.

.PARAMETER AgentPath
    Folder where the FleetPanel agent is installed.
#>

[CmdletBinding()]
param(
    [string]$AgentPath = "C:\FleetAgent"
)

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Error "Run as Administrator."; exit 1 }

function Lock-Path {
    param([string]$Path, [switch]$AllowReadExecute)
    if (-not (Test-Path $Path)) { Write-Host "  (skip, not found) $Path" -ForegroundColor DarkGray; return }

    # Take ownership -> Administrators, then rebuild the ACL from scratch.
    & takeown.exe /F $Path /A /R /D Y | Out-Null

    $acl = Get-Acl $Path
    $acl.SetAccessRuleProtection($true, $false)   # disable inheritance, drop inherited ACEs
    $acl.Access | ForEach-Object { [void]$acl.RemoveAccessRule($_) }

    # SYSTEM + Administrators: full control
    foreach ($who in @("NT AUTHORITY\SYSTEM", "BUILTIN\Administrators")) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $who, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
        $acl.AddAccessRule($rule)
    }

    # Standard Users: read+execute only (or nothing)
    if ($AllowReadExecute) {
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            "BUILTIN\Users", "ReadAndExecute", "ContainerInherit,ObjectInherit", "None", "Allow")
        $acl.AddAccessRule($rule)
    }

    Set-Acl -Path $Path -AclObject $acl
    Write-Host "  locked: $Path" -ForegroundColor Green
}

Write-Host "Locking the hosts file (deny standard-user writes)..." -ForegroundColor Cyan
Lock-Path "$env:SystemRoot\System32\drivers\etc\hosts" -AllowReadExecute

Write-Host "Locking the agent folder (users may run, not modify)..." -ForegroundColor Cyan
Lock-Path $AgentPath -AllowReadExecute

Write-Host "Locking the WDAC policy folder..." -ForegroundColor Cyan
Lock-Path "$env:SystemRoot\System32\CodeIntegrity" -AllowReadExecute

Write-Host ""
Write-Host "Strict permissions applied. Standard users now have read/execute" -ForegroundColor Green
Write-Host "only on these locations and cannot edit or delete them." -ForegroundColor Green
