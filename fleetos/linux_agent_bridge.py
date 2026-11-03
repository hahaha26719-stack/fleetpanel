"""Explicit Linux boundary for the unchanged FleetPanel Windows agent.

This first version intentionally refuses to pretend that Windows registry,
Windows command templates, or Image File Execution Options are enforced on
Linux. Linux policy enforcement must be implemented per policy type and tested
before the OS is used with student accounts.
"""
from __future__ import annotations

import logging
import os
import subprocess

log = logging.getLogger("fleetos.agent_bridge")


def _unsupported(kind: str, detail: str) -> None:
    # Loud, administrator-visible warning. Never silently claim enforcement.
    log.error("UNSUPPORTED LINUX POLICY (%s): %s", kind, detail)


def install(agent_module) -> None:
    """Patch only platform integration functions in memory; source files stay intact."""

    def apply_registry(spec, value):
        _unsupported("registry", f"{spec.get('hive')}\\{spec.get('path')}\\{spec.get('name')}")

    def apply_command(spec, value):
        _unsupported("command", "Windows command-template policies have no Linux equivalent yet")

    def apply_app_block(value):
        _unsupported("app_block", "Windows Image File Execution Options is not available on Linux")

    def apply_web_block(value):
        # The FleetPanel browser checks web_mode before each navigation. This
        # does not block other browsers or system processes, so do not describe
        # it as device-wide web filtering.
        if value:
            _unsupported("web_block", "browser-level filtering is not device-wide Linux enforcement")

    def launch_desktop():
        # The student session is the shell. No Explorer replacement exists.
        log.info("FleetPanel OS shell remains active; no Windows desktop to launch")

    def close_desktop():
        log.info("No separate Windows desktop session exists on FleetPanel OS")

    def reboot():
        # A normal student session should not receive unrestricted reboot power.
        # A privileged system service will be added for authenticated sign-out.
        _unsupported("reboot", "privileged reboot broker has not been implemented")

    agent_module.apply_registry = apply_registry
    agent_module.apply_command = apply_command
    agent_module.apply_app_block = apply_app_block
    agent_module.apply_web_block = apply_web_block
    agent_module.launch_desktop = launch_desktop
    agent_module.close_desktop = close_desktop
    agent_module.reboot = reboot
