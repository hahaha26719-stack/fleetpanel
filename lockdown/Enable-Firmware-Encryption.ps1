<#
.SYNOPSIS
    Closes the offline / physical bypass path: BitLocker + Secure Boot + TPM.

.DESCRIPTION
    WDAC + standard users + strict ACLs stop a logged-in standard user. This
    script closes the remaining route -- booting a DIFFERENT OS from USB to
    edit files offline -- which no in-OS software can stop on its own:

      * BitLocker encrypts the disk, so pulling it out / booting another OS
        yields only ciphertext.
      * Secure Boot (checked) makes firmware refuse unsigned bootloaders.
      * TPM binds the key to this machine's hardware.

    What this script CANNOT do (must be done by a human at the firmware):
      * Set a BIOS/UEFI supervisor password.
      * Disable USB/network boot in firmware.
    These are printed as a checklist at the end.

    Run AS ADMINISTRATOR. Reversible by an admin (manage-bde -off C:) -- by design.
#>

[CmdletBinding()]
param([string]$Drive = "C:")

$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Error "Run as Administrator."; exit 1 }

Write-Host "Checking Secure Boot..." -ForegroundColor Cyan
try {
    $sb = Confirm-SecureBootUEFI
    if ($sb) { Write-Host "  Secure Boot: ENABLED" -ForegroundColor Green }
    else     { Write-Host "  Secure Boot: DISABLED -> enable it in BIOS/UEFI setup." -ForegroundColor Yellow }
} catch { Write-Host "  Secure Boot: not determinable (legacy BIOS?). Enable in firmware." -ForegroundColor Yellow }

Write-Host "Checking TPM..." -ForegroundColor Cyan
try {
    $tpm = Get-Tpm
    if ($tpm.TpmPresent -and $tpm.TpmReady) { Write-Host "  TPM: present & ready" -ForegroundColor Green }
    else { Write-Host "  TPM: not ready -> enable/clear TPM in firmware." -ForegroundColor Yellow }
} catch { Write-Host "  TPM: not available." -ForegroundColor Yellow }

Write-Host "Enabling BitLocker on $Drive (TPM + recovery password)..." -ForegroundColor Cyan
$vol = Get-BitLockerVolume -MountPoint $Drive -ErrorAction SilentlyContinue
if ($vol -and $vol.ProtectionStatus -eq "On") {
    Write-Host "  BitLocker already ON for $Drive." -ForegroundColor Green
} else {
    try {
        Enable-BitLocker -MountPoint $Drive -EncryptionMethod XtsAes256 `
            -UsedSpaceOnly -TpmProtector -ErrorAction Stop | Out-Null
        Add-BitLockerKeyProtector -MountPoint $Drive -RecoveryPasswordProtector | Out-Null
        Write-Host "  BitLocker enabling. SAVE the recovery password now:" -ForegroundColor Green
        (Get-BitLockerVolume -MountPoint $Drive).KeyProtector |
            Where-Object { $_.KeyProtectorType -eq "RecoveryPassword" } |
            Select-Object KeyProtectorId, RecoveryPassword | Format-List
    } catch {
        Write-Host "  Could not enable BitLocker automatically: $_" -ForegroundColor Red
        Write-Host "  Run manually: manage-bde -on $Drive -RecoveryPassword" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== DO THESE BY HAND IN BIOS/UEFI SETUP (no script can) ===" -ForegroundColor Yellow
Write-Host "  [ ] Set a BIOS/UEFI supervisor/admin password" -ForegroundColor Gray
Write-Host "  [ ] Disable booting from USB / CD / network (or require the password)" -ForegroundColor Gray
Write-Host "  [ ] Confirm Secure Boot = Enabled" -ForegroundColor Gray
Write-Host "  [ ] Store BitLocker recovery keys somewhere safe (AD/Intune/Azure)" -ForegroundColor Gray
Write-Host ""
Write-Host "With these done + standard users + WDAC + strict ACLs, the offline" -ForegroundColor Green
Write-Host "and in-OS bypass paths are both closed for non-admin users." -ForegroundColor Green
