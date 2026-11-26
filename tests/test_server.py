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
