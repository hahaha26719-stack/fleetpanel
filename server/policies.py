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

    # ==================================================================== Network
    _reg_bool("hide_network_connections", "Hide Network Connections settings", "Network",
              "HKCU", _EXPLORER_HKCU, "NoNetConnectDisconnect"),
    _reg_bool("disable_file_sharing", "Disable file & printer sharing UI", "Network",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\Network", "NoFileSharingControl"),

    # =========================================================== Applications
    {"key": "blocked_apps", "label": "Blocked applications (comma-separated .exe)",
     "category": "Applications", "type": "value", "apply": {"kind": "app_block"}},

    # ================================================================= Desktop
    _reg_value("set_wallpaper", "Force desktop wallpaper (path)", "Desktop",
               "HKCU", r"Control Panel\Desktop", "Wallpaper"),
    _reg_bool("disable_wallpaper_change", "Prevent changing wallpaper", "Desktop",
              "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Policies\ActiveDesktop",
              "NoChangingWallPaper"),

    # ============================================================ Windows Update
    _reg_bool("disable_windows_update", "Disable automatic Windows Update", "Updates",
              "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", "NoAutoUpdate"),

    # ================================================================== Session
    {"key": "screen_lock_minutes", "label": "Auto-lock screen after N minutes", "category": "Session",
     "type": "value", "apply": {"kind": "command", "template": "powercfg /change monitor-timeout-ac {value}"}},
]

POLICY_INDEX = {p["key"]: p for p in POLICIES}


def categories():
    cats = {}
    for p in POLICIES:
        cats.setdefault(p["category"], []).append(p)
    return cats
