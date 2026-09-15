"""
Policy catalog.

Each policy has:
  key      - stable identifier stored in DB and sent to agents
  label    - human name shown in the panel
  category - grouping for the UI
  type     - "bool" (on/off) or "value" (needs a value, e.g. wallpaper path)
  apply    - how the Windows agent enforces it. Supported "kind"s:
               registry    - set a registry value (hive/path/name/regtype; on/off for bools)
               command     - run a shell command; {value} is substituted
               app_block   - block listed .exe names from launching
               web_block   - block listed domains/URLs via the hosts file
             The catalog is the single source of truth read by agent/agent.py.

To add a policy, add one entry here — the panel and agent pick it up automatically.
"""


def _reg_bool(key, label, category, hive, path, name, on=1, off=0):
    return {"key": key, "label": label, "category": category, "type": "bool",
            "apply": {"kind": "registry", "hive": hive, "path": path, "name": name,
                      "on": on, "off": off, "regtype": "REG_DWORD"}}


def _reg_value(key, label, category, hive, path, name, regtype="REG_SZ"):
    return {"key": key, "label": label, "category": category, "type": "value",
            "apply": {"kind": "registry", "hive": hive, "path": path, "name": name,
                      "regtype": regtype}}


_EXPLORER_HKCU = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
_SYSTEM_HKCU = r"Software\Microsoft\Windows\CurrentVersion\Policies\System"

POLICIES = [
    # =========================================================== Web restrictions
    {"key": "blocked_websites",
     "label": "Blocked websites (comma-separated domains, e.g. facebook.com, tiktok.com)",
     "category": "Web Restrictions", "type": "value",
     "apply": {"kind": "web_block"}},
    _reg_value("browser_homepage", "Force browser homepage (URL)", "Web Restrictions",
               "HKLM", r"SOFTWARE\Policies\Google\Chrome", "HomepageLocation"),
    _reg_bool("chrome_incognito_off", "Disable Chrome Incognito mode", "Web Restrictions",
              "HKLM", r"SOFTWARE\Policies\Google\Chrome", "IncognitoModeAvailability", on=1, off=0),
    _reg_bool("edge_inprivate_off", "Disable Edge InPrivate mode", "Web Restrictions",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Edge", "InPrivateModeAvailability", on=1, off=0),
    _reg_value("chrome_url_allowlist", "Chrome: only allow these URLs (comma-separated)",
               "Web Restrictions", "HKLM", r"SOFTWARE\Policies\Google\Chrome\URLAllowlist", "1"),
    _reg_value("chrome_url_blocklist", "Chrome: blocked URLs (enterprise policy, standard-user-proof)",
               "Web Restrictions", "HKLM", r"SOFTWARE\Policies\Google\Chrome\URLBlocklist", "1"),
    _reg_value("edge_url_blocklist", "Edge: blocked URLs (enterprise policy)",
               "Web Restrictions", "HKLM", r"SOFTWARE\Policies\Microsoft\Edge\URLBlocklist", "1"),
    _reg_value("edge_homepage", "Force Edge homepage (URL)", "Web Restrictions",
               "HKLM", r"SOFTWARE\Policies\Microsoft\Edge", "HomepageLocation"),
    _reg_bool("chrome_safe_search", "Chrome: force Google SafeSearch", "Web Restrictions",
              "HKLM", r"SOFTWARE\Policies\Google\Chrome", "ForceGoogleSafeSearch"),
    _reg_bool("edge_safe_search", "Edge: force SafeSearch", "Web Restrictions",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Edge", "ForceSafeSearch"),
    _reg_value("youtube_restrict", "Force YouTube Restricted Mode (Strict/Moderate)", "Web Restrictions",
               "HKLM", r"SOFTWARE\Policies\Google\Chrome", "ForceYouTubeRestrict", regtype="REG_DWORD"),
    _reg_bool("chrome_block_extensions", "Chrome: block installing extensions", "Web Restrictions",
              "HKLM", r"SOFTWARE\Policies\Google\Chrome", "ExtensionInstallBlocklist"),
    _reg_bool("chrome_disable_dev_tools", "Chrome: disable Developer Tools", "Web Restrictions",
              "HKLM", r"SOFTWARE\Policies\Google\Chrome", "DeveloperToolsAvailability", on=2, off=0),
    _reg_bool("chrome_disable_guest", "Chrome: disable Guest mode", "Web Restrictions",
              "HKLM", r"SOFTWARE\Policies\Google\Chrome", "BrowserGuestModeEnabled", on=0, off=1),

    # ==================================================================== Printing
    _reg_bool("disable_printing", "Disable printing (block Print dialog)", "Printing",
              "HKCU", _EXPLORER_HKCU, "NoPrinting"),
    _reg_bool("disable_add_printer", "Prevent adding printers", "Printing",
              "HKCU", _EXPLORER_HKCU, "NoAddPrinter"),
    _reg_bool("disable_delete_printer", "Prevent deleting printers", "Printing",
              "HKCU", _EXPLORER_HKCU, "NoDeletePrinter"),
    {"key": "disable_print_spooler", "label": "Stop & disable Print Spooler service",
     "category": "Printing", "type": "bool",
     "apply": {"kind": "registry", "hive": "HKLM",
               "path": r"SYSTEM\CurrentControlSet\Services\Spooler",
               "name": "Start", "on": 4, "off": 2, "regtype": "REG_DWORD"}},
    _reg_bool("point_and_print_restrict", "Restrict Point-and-Print to admins", "Printing",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint",
              "RestrictDriverInstallationToAdministrators", on=1, off=0),
    _reg_bool("disable_web_printing", "Block printing to web/Internet printers", "Printing",
              "HKCU", _EXPLORER_HKCU, "NoWebPrinting"),
    _reg_bool("no_printer_tab", "Hide the Printers tab in settings", "Printing",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows NT\Printers", "NoPrinterTabs"),
    _reg_bool("disable_xps_printer", "Disable Microsoft XPS Document Writer", "Printing",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows NT\Printers", "DisableXPSPrinting"),

    # =============================================================== File Explorer
    _reg_bool("hide_all_drives", "Hide ALL drives in Explorer", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoDrives", on=0x3FFFFFF, off=0),
    _reg_bool("hide_c_drive", "Hide C: drive only", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoDrives", on=4, off=0),
    _reg_bool("no_drive_access", "Block access to ALL drives (deny open)", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoViewOnDrive", on=0x3FFFFFF, off=0),
    _reg_bool("disable_context_menu", "Disable right-click context menu", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoViewContextMenu"),
    _reg_bool("hide_network", "Hide Network in Explorer", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoNetHood"),
    _reg_bool("hide_recycle_bin", "Hide Recycle Bin", "File Explorer",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\NonEnum",
              "{645FF040-5081-101B-9F08-00AA002F954E}"),
    _reg_bool("no_folder_options", "Remove Folder Options menu", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoFolderOptions"),
    _reg_bool("no_file_menu", "Remove File menu in Explorer", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoFileMenu"),
    _reg_bool("disable_thumb_cache", "Disable thumbnail caching", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "DisableThumbnailCache"),
    _reg_bool("hide_hidden_files", "Force hidden files to stay hidden", "File Explorer",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Hidden",
              on=2, off=1),
    _reg_bool("hide_file_extensions", "Hide file extensions", "File Explorer",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "HideFileExt"),
    _reg_bool("no_new_folder", "Remove 'New Folder' from context menu", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoNewFolderButton"),
    _reg_bool("no_recent_docs", "Do not track recently opened documents", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoRecentDocsHistory"),
    _reg_bool("clear_recent_on_exit", "Clear recent documents on logoff", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "ClearRecentDocsOnExit"),
    _reg_bool("no_search_files", "Disable search from Explorer", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoFind"),
    _reg_bool("no_hardware_tab", "Hide Hardware tab in drive properties", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoHardwareTab"),
    _reg_bool("no_security_tab", "Hide Security tab in file/folder properties", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoSecurityTab"),
    _reg_bool("no_manage_context", "Remove 'Manage' from This PC context menu", "File Explorer",
              "HKCU", _EXPLORER_HKCU, "NoManageMyComputerVerb"),

    # ============================================================= Removable media
    {"key": "block_usb_storage", "label": "Block USB storage devices", "category": "Removable Media",
     "type": "bool",
     "apply": {"kind": "registry", "hive": "HKLM",
               "path": r"SYSTEM\CurrentControlSet\Services\USBSTOR",
               "name": "Start", "on": 4, "off": 3, "regtype": "REG_DWORD"}},
    _reg_bool("readonly_removable", "Removable disks: read-only", "Removable Media",
              "HKLM", r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies", "WriteProtect"),
    _reg_bool("deny_removable_read", "Deny read access to removable disks", "Removable Media",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices\{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}",
              "Deny_Read"),
    _reg_bool("deny_removable_write", "Deny write access to removable disks", "Removable Media",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices\{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}",
              "Deny_Write"),
    _reg_bool("deny_all_removable", "Deny ALL access to all removable storage classes", "Removable Media",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices",
              "Deny_All"),
    _reg_bool("deny_cd_dvd_write", "Deny write to CD/DVD drives", "Removable Media",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices\{53f56308-b6bf-11d0-94f2-00a0c91efb8b}",
              "Deny_Write"),
    {"key": "disable_autorun", "label": "Disable AutoRun/AutoPlay on all drives",
     "category": "Removable Media", "type": "bool",
     "apply": {"kind": "registry", "hive": "HKLM",
               "path": r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer",
               "name": "NoDriveTypeAutoRun", "on": 0xFF, "off": 0, "regtype": "REG_DWORD"}},
    {"key": "block_wpd_devices", "label": "Block phones/media players (WPD devices)",
     "category": "Removable Media", "type": "bool",
     "apply": {"kind": "registry", "hive": "HKLM",
               "path": r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices\{6AC27878-A6FA-4155-BA85-F98F491D4F33}",
               "name": "Deny_All", "on": 1, "off": 0, "regtype": "REG_DWORD"}},

    # =================================================================== Start/UI
    _reg_bool("disable_run", "Remove Run menu", "Start & Taskbar",
              "HKCU", _EXPLORER_HKCU, "NoRun"),
    _reg_bool("hide_search", "Hide taskbar search box", "Start & Taskbar",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Search", "SearchboxTaskbarMode",
              on=0, off=1),
    _reg_bool("lock_taskbar", "Lock the taskbar", "Start & Taskbar",
              "HKCU", _EXPLORER_HKCU, "LockTaskbar"),
    _reg_bool("no_change_startmenu", "Prevent changes to Start menu & taskbar", "Start & Taskbar",
              "HKCU", _EXPLORER_HKCU, "NoSetTaskbar"),
    _reg_bool("no_taskmgr_taskbar", "Remove Task Manager from taskbar menu", "Start & Taskbar",
              "HKCU", _EXPLORER_HKCU, "NoTrayContextMenu"),
    _reg_bool("no_shutdown", "Remove Shut Down / Restart options", "Start & Taskbar",
              "HKCU", _EXPLORER_HKCU, "NoClose"),
    _reg_bool("no_logoff", "Remove Log Off from Start menu", "Start & Taskbar",
              "HKCU", _EXPLORER_HKCU, "StartMenuLogOff"),
    _reg_bool("hide_widgets", "Hide Widgets button (Win11)", "Start & Taskbar",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Dsh", "AllowNewsAndInterests", on=0, off=1),
    _reg_bool("disable_cortana", "Disable Cortana", "Start & Taskbar",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "AllowCortana", on=0, off=1),
    _reg_bool("hide_task_view", "Hide Task View button", "Start & Taskbar",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowTaskViewButton",
              on=0, off=1),
    _reg_bool("disable_notifications", "Disable notification center", "Start & Taskbar",
              "HKCU", _EXPLORER_HKCU, "DisableNotificationCenter"),

    # =================================================================== Security
    _reg_bool("disable_task_manager", "Disable Task Manager", "Security",
              "HKCU", _SYSTEM_HKCU, "DisableTaskMgr"),
    _reg_bool("disable_regedit", "Disable Registry Editor", "Security",
              "HKCU", _SYSTEM_HKCU, "DisableRegistryTools"),
    {"key": "disable_cmd", "label": "Disable Command Prompt", "category": "Security", "type": "bool",
     "apply": {"kind": "registry", "hive": "HKCU", "path": r"Software\Policies\Microsoft\Windows\System",
               "name": "DisableCMD", "on": 2, "off": 0, "regtype": "REG_DWORD"}},
    _reg_bool("hide_control_panel", "Hide Control Panel & Settings", "Security",
              "HKCU", _EXPLORER_HKCU, "NoControlPanel"),
    _reg_bool("disable_lockscreen_camera", "Disable lock-screen camera", "Security",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Personalization", "NoLockScreenCamera"),
    _reg_bool("disable_powershell", "Disable PowerShell (block via app-block instead is stronger)", "Security",
              "HKCU", r"Software\Policies\Microsoft\Windows\PowerShell", "EnableScripts", on=0, off=1),
    _reg_bool("disable_mmc", "Disable Microsoft Management Console (MMC)", "Security",
              "HKCU", r"Software\Policies\Microsoft\MMC", "RestrictToPermittedSnapins"),
    _reg_bool("disable_control_run", "Prevent running Control Panel applets", "Security",
              "HKCU", _EXPLORER_HKCU, "DisallowCpl"),
    _reg_bool("no_change_password", "Remove 'Change Password' (Ctrl+Alt+Del)", "Security",
              "HKCU", _SYSTEM_HKCU, "DisableChangePassword"),
    _reg_bool("no_lock_workstation", "Remove 'Lock Computer' option", "Security",
              "HKCU", _SYSTEM_HKCU, "DisableLockWorkstation"),
    _reg_bool("hide_fast_user_switch", "Hide Switch User / fast user switching", "Security",
              "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "HideFastUserSwitching"),
    _reg_bool("disable_defender_off", "Prevent disabling Windows Defender (recommended ON)", "Security",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows Defender", "DisableAntiSpyware", on=0, off=0),
    _reg_bool("require_ctrl_alt_del", "Require Ctrl+Alt+Del at logon", "Security",
              "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "DisableCAD", on=0, off=1),
    _reg_bool("dont_display_last_user", "Do not display last signed-in user", "Security",
              "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "DontDisplayLastUserName"),
    _reg_value("legal_notice_caption", "Logon banner: title", "Security",
               "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "legalnoticecaption"),
    _reg_value("legal_notice_text", "Logon banner: message text", "Security",
               "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "legalnoticetext"),

    # ==================================================================== Network
    _reg_bool("hide_network_connections", "Hide Network Connections settings", "Network",
              "HKCU", _EXPLORER_HKCU, "NoNetConnectDisconnect"),
    _reg_bool("disable_file_sharing", "Disable file & printer sharing UI", "Network",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Network", "NoFileSharingControl"),
    _reg_value("proxy_server", "Force proxy server (host:port)", "Network",
               "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", "ProxyServer"),
    _reg_bool("proxy_enable", "Enable the forced proxy", "Network",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Internet Settings", "ProxyEnable"),
    _reg_bool("no_proxy_change", "Prevent changing proxy settings", "Network",
              "HKCU", r"Software\Policies\Microsoft\Internet Explorer\Control Panel", "Proxy"),
    _reg_bool("disable_wifi_sense", "Disable Wi-Fi Sense", "Network",
              "HKLM", r"SOFTWARE\Microsoft\PolicyManager\default\WiFi\AllowWiFiHotSpotReporting", "value",
              on=0, off=1),
    _reg_bool("disable_bluetooth", "Disable Bluetooth service", "Network",
              "HKLM", r"SYSTEM\CurrentControlSet\Services\bthserv", "Start", on=4, off=2),
    _reg_bool("disable_ics", "Disable Internet Connection Sharing", "Network",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Network Connections", "NC_ShowSharedAccessUI",
              on=0, off=1),

    # =========================================================== Applications
    {"key": "blocked_apps", "label": "Blocked applications (comma-separated .exe)",
     "category": "Applications", "type": "value", "apply": {"kind": "app_block"}},
    _reg_bool("disable_store", "Disable Microsoft Store", "Applications",
              "HKLM", r"SOFTWARE\Policies\Microsoft\WindowsStore", "RemoveWindowsStore"),
    _reg_bool("disable_installer", "Block Windows Installer (MSI) for non-admins", "Applications",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Installer", "DisableMSI", on=2, off=0),
    _reg_bool("no_run_only_allowed", "Only allow explicitly listed apps (RestrictRun)", "Applications",
              "HKCU", _EXPLORER_HKCU, "RestrictRun"),
    _reg_bool("disable_task_scheduler", "Disable Task Scheduler UI", "Applications",
              "HKCU", r"Software\Policies\Microsoft\Windows\Task Scheduler5.0", "Disable Task Scheduler"),

    # ================================================================= Desktop
    _reg_value("set_wallpaper", "Force desktop wallpaper (path)", "Desktop",
               "HKCU", r"Control Panel\Desktop", "Wallpaper"),
    _reg_value("wallpaper_style", "Wallpaper style (0=center,2=stretch,6=fit,10=fill)", "Desktop",
               "HKCU", r"Control Panel\Desktop", "WallpaperStyle"),
    _reg_bool("disable_wallpaper_change", "Prevent changing wallpaper", "Desktop",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\ActiveDesktop",
              "NoChangingWallPaper"),
    _reg_bool("no_screensaver_change", "Prevent changing screen saver", "Desktop",
              "HKCU", r"Software\Policies\Microsoft\Windows\Control Panel\Desktop", "ScreenSaveActive"),
    _reg_bool("hide_desktop_icons", "Hide all desktop icons", "Desktop",
              "HKCU", _EXPLORER_HKCU, "NoDesktop"),
    _reg_bool("no_prop_my_computer", "Remove Properties from This PC", "Desktop",
              "HKCU", _EXPLORER_HKCU, "NoPropertiesMyComputer"),
    _reg_bool("force_screensaver_lock", "Force password on screen saver resume", "Desktop",
              "HKCU", r"Software\Policies\Microsoft\Windows\Control Panel\Desktop", "ScreenSaverIsSecure"),

    # ============================================================ Windows Update
    _reg_bool("disable_windows_update", "Disable automatic Windows Update", "Updates",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoUpdate"),
    _reg_bool("no_reboot_with_users", "No auto-reboot with logged-on users", "Updates",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoRebootWithLoggedOnUsers"),
    _reg_value("update_defer_days", "Defer feature updates N days", "Updates",
               "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate", "DeferFeatureUpdatesPeriodInDays",
               regtype="REG_DWORD"),
    _reg_bool("disable_driver_updates", "Exclude drivers from Windows Update", "Updates",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate", "ExcludeWUDriversInQualityUpdate"),

    # =============================================================== Privacy
    _reg_bool("disable_telemetry", "Disable telemetry / diagnostic data", "Privacy",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", on=0, off=3),
    _reg_bool("disable_advertising_id", "Disable advertising ID", "Privacy",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo", "DisabledByGroupPolicy"),
    _reg_bool("disable_location", "Disable location services", "Privacy",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors", "DisableLocation"),
    _reg_bool("disable_camera", "Disable the camera", "Privacy",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Camera", "AllowCamera", on=0, off=1),
    _reg_bool("disable_microphone_access", "Deny apps access to microphone", "Privacy",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\AppPrivacy", "LetAppsAccessMicrophone",
              on=2, off=0),
    _reg_bool("disable_activity_history", "Disable activity history / timeline", "Privacy",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", on=0, off=1),
    _reg_bool("disable_clipboard_history", "Disable clipboard history", "Privacy",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "AllowClipboardHistory", on=0, off=1),

    # ======================================================= Control Panel / Settings
    _reg_value("restrict_cpl_only", "Only show these Control Panel applets (comma-separated)",
               "Control Panel & Settings", "HKCU", _EXPLORER_HKCU, "RestrictCpl"),
    _reg_value("hide_settings_pages", "Hide specific Settings pages (e.g. hide:windowsupdate)",
               "Control Panel & Settings", "HKLM",
               r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer", "SettingsPageVisibility"),
    _reg_bool("no_display_settings", "Block Display settings", "Control Panel & Settings",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\System", "NoDispCPL"),
    _reg_bool("no_add_remove_programs", "Hide Add/Remove Programs", "Control Panel & Settings",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Uninstall", "NoAddRemovePrograms"),
    _reg_bool("no_datetime_change", "Prevent changing date & time", "Control Panel & Settings",
              "HKCU", _EXPLORER_HKCU, "NoChangeDateTime"),

    # ================================================================== Session
    {"key": "screen_lock_minutes", "label": "Auto-lock screen after N minutes", "category": "Session",
     "type": "value", "apply": {"kind": "command", "template": "powercfg /change monitor-timeout-ac {value}"}},
    _reg_value("inactivity_lock_secs", "Lock after N seconds of inactivity", "Session",
               "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
               "InactivityTimeoutSecs", regtype="REG_DWORD"),
    _reg_value("max_disconnection_min", "Log off idle session after N minutes (value in ms)", "Session",
               "HKCU", r"Software\Policies\Microsoft\Windows\Control Panel\Desktop",
               "ScreenSaveTimeOut"),
    {"key": "force_logoff_time", "label": "Run a command at a set time (e.g. shutdown)",
     "category": "Session", "type": "value",
     "apply": {"kind": "command", "template": "{value}"}},
]

POLICY_INDEX = {p["key"]: p for p in POLICIES}


def categories():
    cats = {}
    for p in POLICIES:
        cats.setdefault(p["category"], []).append(p)
    return cats
