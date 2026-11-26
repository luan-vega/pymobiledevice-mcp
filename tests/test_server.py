import subprocess
import sys
from unittest.mock import patch

import pytest

from pymobiledevice_mcp import runner, server


def completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def mock_run():
    with patch("pymobiledevice_mcp.runner.subprocess.run") as m:
        m.return_value = completed(stdout="ok")
        yield m


def called_args(mock_run):
    return mock_run.call_args.args[0]


def test_uses_same_interpreter_without_shell(mock_run):
    server.list_devices()
    cmd = called_args(mock_run)
    assert cmd[:3] == [sys.executable, "-m", "pymobiledevice3"]
    assert cmd[3:] == ["usbmux", "list"]
    assert "shell" not in mock_run.call_args.kwargs


def test_udid_is_passed(mock_run):
    server.battery_diagnostics(udid="00008110-ABC")
    assert called_args(mock_run)[3:] == ["diagnostics", "battery", "single", "--udid", "00008110-ABC"]


def test_developer_tools_use_tunnel(mock_run):
    server.process_cpu_memory()
    assert called_args(mock_run)[3:] == ["developer", "dvt", "sysmon", "process", "single", "--tunnel", ""]


def test_nonzero_exit_is_reported(mock_run):
    mock_run.return_value = completed(stderr="No module named pymobiledevice3", returncode=1)
    out = server.device_info()
    assert "[exit code 1]" in out
    assert "pip install" in out


def test_timeout_is_reported(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=1)
    assert "timeout" in server.process_list()


def test_output_is_truncated(mock_run):
    mock_run.return_value = completed(stdout="x" * (runner.MAX_OUTPUT_CHARS + 50))
    out = server.crash_reports()
    assert out.endswith("omitidos]")
    assert len(out) < runner.MAX_OUTPUT_CHARS + 100


def test_syslog_snapshot_filters_partial_output(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(
        cmd="x", timeout=5, output="kernel: jetsam killed App\nSpringBoard: hello\n"
    )
    out = server.syslog_snapshot(seconds=5, contains="JETSAM")
    assert out == "kernel: jetsam killed App"


def test_syslog_snapshot_clamps_seconds(mock_run):
    server.syslog_snapshot(seconds=999)
    assert mock_run.call_args.kwargs["timeout"] == 60


# --- Ações de melhoria ------------------------------------------------------

@pytest.fixture
def actions_on(monkeypatch):
    monkeypatch.setenv("PMD3_MCP_ALLOW_ACTIONS", "1")


def test_actions_disabled_by_default(mock_run, monkeypatch):
    monkeypatch.delenv("PMD3_MCP_ALLOW_ACTIONS", raising=False)
    out = server.restart_device(confirm=True)
    assert "desativadas" in out
    mock_run.assert_not_called()


def test_actions_without_confirm_only_preview(mock_run, actions_on):
    out = server.uninstall_app("com.example.game")
    assert out.startswith("PRÉVIA")
    mock_run.assert_not_called()


def test_uninstall_with_confirm_runs(mock_run, actions_on):
    server.uninstall_app("com.example.game", confirm=True, udid="ABC")
    assert called_args(mock_run)[3:] == ["apps", "uninstall", "com.example.game", "--udid", "ABC"]


@pytest.mark.parametrize("bad", ["com.apple.mobilesafari", "foo; rm -rf", "semponto"])
def test_uninstall_rejects_bad_or_system_ids(mock_run, actions_on, bad):
    assert server.uninstall_app(bad, confirm=True).startswith("ERRO")
    mock_run.assert_not_called()


def test_kill_process_uses_tunnel(mock_run, actions_on):
    server.kill_process(1234, confirm=True)
    assert called_args(mock_run)[3:] == ["developer", "dvt", "kill", "1234", "--tunnel", ""]


def test_kill_process_rejects_launchd(mock_run, actions_on):
    assert server.kill_process(1, confirm=True).startswith("ERRO")
    mock_run.assert_not_called()


def test_clear_crash_and_restart(mock_run, actions_on):
    server.clear_crash_reports(confirm=True)
    assert called_args(mock_run)[3:] == ["crash", "clear"]
    server.restart_device(confirm=True)
    assert called_args(mock_run)[3:] == ["diagnostics", "restart"]


def test_installed_apps_sorted_by_size(mock_run):
    import json
    data = {
        "com.small": {"ApplicationType": "User", "CFBundleDisplayName": "Small",
                      "StaticDiskUsage": 10 * 1048576, "DynamicDiskUsage": 0},
        "com.big": {"ApplicationType": "User", "CFBundleDisplayName": "Big",
                    "StaticDiskUsage": 100 * 1048576, "DynamicDiskUsage": 900 * 1048576},
        "com.apple.x": {"ApplicationType": "System"},
    }
    mock_run.return_value = completed(stdout=json.dumps(data))
    lines = server.installed_apps().splitlines()
    assert "Big" in lines[1] and "1,000 MB" in lines[1]
    assert "Small" in lines[2]
    assert not any("com.apple.x" in l for l in lines)


def test_installed_apps_falls_back_to_raw(mock_run):
    mock_run.return_value = completed(stdout="formato inesperado")
    assert server.installed_apps() == "formato inesperado"
