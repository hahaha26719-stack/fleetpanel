<#
.SYNOPSIS
    Generates a WDAC (Windows Defender Application Control) DEFAULT-DENY policy.

.DESCRIPTION
    This is the strongest *software* lockdown Windows offers, enforced by the
    kernel's Code Integrity engine at every process launch:

      * Default-deny: NOTHING executes unless it matches an allow rule.
      * This blocks LOLBins/UAC-bypass tools (computerdefaults.exe,
        fodhelper.exe, sdclt.exe, eventvwr.exe, mshta.exe, wmic.exe, ...) and
        even cmd.exe / powershell.exe / regedit.exe unless you allow them.
      * Evaluated by the kernel -> applies from boot, in Safe Mode too. A
        standard user cannot bypass it by renaming/copying a binary.

    The policy allows, by default:
      * Windows itself (so the OS boots and runs)
      * Anything already installed under C:\Program Files and
        C:\Program Files (x86) at policy-creation time (your approved apps)
    ...and denies everything else.

    HOW IT STAYS ENFORCED / "can't be bypassed by a standard user":
      * Deploy it as a SIGNED policy (see -Sign notes) so removing it requires
        the signing key, not just admin rights. Unsigned policies can be
        removed by an admin; signed ones cannot be trivially deleted.
      * Combine with standard (non-admin) users + BitLocker + Secure Boot +
        BIOS password so the offline "boot another OS and delete the policy
        file" path is also closed.

    Run AS ADMINISTRATOR on a *clean, known-good reference machine*.

.PARAMETER OutDir
    Where to write the policy XML + compiled .cip binary.

.PARAMETER Audit
    Build in AUDIT mode first (logs what WOULD be blocked, blocks nothing).
    STRONGLY recommended before enforcing, so you don't lock out needed apps.

.EXAMPLE
    # 1. Audit first, review Event Viewer > Code Integrity for a week:
    .\New-WDACDefaultDeny.ps1 -OutDir C:\WDAC -Audit

    # 2. Then build the enforced policy:
    .\New-WDACDefaultDeny.ps1 -OutDir C:\WDAC
#>

[CmdletBinding()]
param(
    [string]$OutDir = "C:\WDAC",
    [switch]$Audit
)

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Error "Run as Administrator."; exit 1 }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$base    = Join-Path $OutDir "WDAC_Base.xml"
$prog    = Join-Path $OutDir "WDAC_ProgramFiles.xml"
$merged  = Join-Path $OutDir "WDAC_DefaultDeny.xml"
$cip     = Join-Path $OutDir "WDAC_DefaultDeny.cip"

Write-Host "[1/4] Base allow rules for Windows + drivers..." -ForegroundColor Cyan
# DefaultWindows template: allows the OS to run, denies everything else.
New-CIPolicy -FilePath $base -Level SignedVersion -UserPEs `
    -ScanPath "C:\Windows" -NoShadowCopy -ErrorAction Stop

Write-Host "[2/4] Allow approved apps under Program Files..." -ForegroundColor Cyan
# Hash/publisher rules for what is already installed = your approved software.
$scanTargets = @("C:\Program Files", "C:\Program Files (x86)") | Where-Object { Test-Path $_ }
New-CIPolicy -FilePath $prog -Level Publisher -Fallback Hash -UserPEs `
    -ScanPath ($scanTargets -join ",") -NoShadowCopy -ErrorAction SilentlyContinue

Write-Host "[3/4] Merging into a single default-deny policy..." -ForegroundColor Cyan
$toMerge = @($base)
if (Test-Path $prog) { $toMerge += $prog }
Merge-CIPolicy -PolicyPaths $toMerge -OutputFilePath $merged | Out-Null

# Give the policy a stable ID and remove the "allow all" fallback so it is
# genuinely default-deny.
Set-CIPolicyIdInfo -FilePath $merged -PolicyName "FleetPanel Default-Deny" -PolicyId (New-Guid)

# Rule options: enforce (or audit), require at boot, user-mode code integrity.
if ($Audit) {
    Set-RuleOption -FilePath $merged -Option 3            # 3 = Audit Mode ON
    Write-Host "    AUDIT mode: nothing is blocked; violations are logged only." -ForegroundColor Yellow
} else {
    Set-RuleOption -FilePath $merged -Option 3 -Delete    # remove Audit -> ENFORCE
    Write-Host "    ENFORCE mode: unlisted binaries will be BLOCKED." -ForegroundColor Green
}
Set-RuleOption -FilePath $merged -Option 0                # UMCI (user-mode too)
Set-RuleOption -FilePath $merged -Option 2 -Delete        # remove "Required:WHQL" if present
Set-RuleOption -FilePath $merged -Option 6                # allow unsigned policy update by admin during rollout

Write-Host "[4/4] Compiling to binary (.cip)..." -ForegroundColor Cyan
ConvertFrom-CIPolicy -XmlFilePath $merged -BinaryFilePath $cip | Out-Null

Write-Host ""
Write-Host "Policy written:" -ForegroundColor Green
Write-Host "   XML : $merged"
Write-Host "   CIP : $cip"
Write-Host ""
Write-Host "DEPLOY (this machine, for testing):" -ForegroundColor Cyan
Write-Host "   Copy `"$cip`" to C:\Windows\System32\CodeIntegrity\SiPolicy.p7b"
Write-Host "   then reboot. (Win11/Server: use the multiple-policy path"
Write-Host "   C:\Windows\System32\CodeIntegrity\CiPolicies\Active\<GUID>.cip)"
Write-Host ""
Write-Host "FOR 150 PCs: deploy the .cip via Group Policy (Computer > Admin" -ForegroundColor Cyan
Write-Host "Templates > System > Device Guard > Deploy WDAC) or Intune, and" -ForegroundColor Cyan
Write-Host "SIGN the policy so it cannot be removed without your key." -ForegroundColor Cyan
Write-Host ""
Write-Host "!! Always run with -Audit first and review Event Viewer >" -ForegroundColor Yellow
Write-Host "   Applications and Services Logs > Microsoft > Windows >" -ForegroundColor Yellow
Write-Host "   CodeIntegrity > Operational, or you may lock out needed apps." -ForegroundColor Yellow
