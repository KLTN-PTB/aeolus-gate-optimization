"""Windows launcher checks that never start the server, browser or editor."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
LAUNCHER=ROOT/"scripts/start_web_dashboard.cmd"
POWERSHELL=Path(os.environ.get("SystemRoot",r"C:\Windows"))/"System32/WindowsPowerShell/v1.0/powershell.exe"
pytestmark=pytest.mark.skipif(sys.platform!="win32",reason="Windows launchers")


def run_hidden(args,cwd):
    return subprocess.run(args,cwd=cwd,text=True,capture_output=True,timeout=30,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def test_cmd_launcher_uses_check_mode_from_another_working_directory(tmp_path):
    work=tmp_path/"working directory with spaces";work.mkdir()
    result=run_hidden([os.environ.get("COMSPEC",r"C:\Windows\System32\cmd.exe"),"/d","/c",
                       str(LAUNCHER),"-Check","-Port","8123"],work)
    assert result.returncode==0,result.stdout+result.stderr
    assert "http://127.0.0.1:8123" in result.stdout
    assert "CHECK PASSED. No server, browser, notebook, or editor was started." in result.stdout
    assert str(ROOT) in result.stdout


def test_explicit_powershell_check_does_not_use_file_association():
    result=run_hidden([str(POWERSHELL),"-NoProfile","-ExecutionPolicy","Bypass","-File",
                       str(ROOT/"scripts/start_web_dashboard.ps1"),"-Check"],ROOT)
    assert result.returncode==0,result.stdout+result.stderr
    assert "CHECK PASSED" in result.stdout


def test_check_rejects_setup_or_build_before_any_installation():
    for flag in ("-Setup","-Build"):
        result=run_hidden([str(POWERSHELL),"-NoProfile","-File",
                           str(ROOT/"scripts/start_web_dashboard.ps1"),"-Check",flag],ROOT)
        assert result.returncode!=0
        assert "-Check is read-only" in result.stdout+result.stderr


def test_cmd_propagates_invalid_port_failure():
    result=run_hidden([os.environ.get("COMSPEC",r"C:\Windows\System32\cmd.exe"),"/d","/c",
                       str(LAUNCHER),"-Check","-Port","0"],ROOT)
    assert result.returncode!=0
    assert "CHECK PASSED" not in result.stdout
