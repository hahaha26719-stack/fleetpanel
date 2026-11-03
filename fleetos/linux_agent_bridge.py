"""Linux boundary for the unchanged Windows-era FleetPanel agent.

Windows registry, IFEO, command-template and device-wide web policies are
rejected rather than falsely reported as enforced. A privileged, tested Linux
policy service is required before student deployment.
"""
from __future__ import annotations
import logging
import os
import sys
log = logging.getLogger("fleetos.agent_bridge")
def _unsupported(kind: str, detail: str = "") -> None:
    message = f"{kind} policy is not implemented on FleetOS"
    if detail: message += f": {detail}"
    log.error(message)
    raise NotImplementedError(message)
def install(agent_module) -> None:
    def apply_registry(spec, value):
        _unsupported("Windows registry", f"{spec.get('hive')}\\{spec.get('path')}")
    def apply_command(spec, value):
        _unsupported("Windows command template")
    def apply_app_block(value):
        _unsupported("Windows executable block list")
    def apply_web_block(value):
        _unsupported("device-wide web filtering")
    def launch_desktop():
        # No alternate desktop is exposed to student sessions. The kiosk
        # service restarts this shell if an administrator exits it.
        log.warning("No separate desktop is configured on FleetOS")
    def close_desktop():
        log.info("No separate Windows desktop session exists")
    def restart_shell():
        # The original launcher calls agent.reboot() after sign-out. On FleetOS
        # this means restarting the student shell, not rebooting the device.
        entry = os.path.abspath(sys.argv[0])
        log.info("Restarting FleetPanel shell after sign-out")
        os.execv(sys.executable, [sys.executable, entry])
    agent_module.apply_registry = apply_registry
    agent_module.apply_command = apply_command
    agent_module.apply_app_block = apply_app_block
    agent_module.apply_web_block = apply_web_block
    agent_module.launch_desktop = launch_desktop
    agent_module.close_desktop = close_desktop
    agent_module.reboot = restart_shell
