import types
import pytest
from fleetos import linux_agent_bridge

def test_bridge_replaces_windows_integration_without_touching_source():
    agent = types.SimpleNamespace()
    linux_agent_bridge.install(agent)
    with pytest.raises(NotImplementedError):
        agent.apply_registry({"hive": "HKLM", "path": "Software", "name": "x"}, 1)
    with pytest.raises(NotImplementedError):
        agent.apply_command({"template": "echo {value}"}, "x")
    with pytest.raises(NotImplementedError):
        agent.apply_app_block("bad.exe")
    with pytest.raises(NotImplementedError):
        agent.apply_web_block("example.com")
    with pytest.raises(NotImplementedError):
        agent.reboot()

def test_non_privileged_desktop_hooks_are_safe(caplog):
    agent = types.SimpleNamespace()
    linux_agent_bridge.install(agent)
    agent.launch_desktop()
    agent.close_desktop()
