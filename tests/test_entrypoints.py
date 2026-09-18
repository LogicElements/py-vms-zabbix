"""Tests of the package skeleton: one distribution brings both the service and
the tray application, each with its own entry point (UC1-R1)."""

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INSTALLER = ROOT / "offline" / "install.ps1"


@pytest.fixture(scope="module")
def pyproject():
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_service_entry_point_is_declared(pyproject):
    """UC1-R1: the service has a console entry point of its own."""
    assert pyproject["project"]["scripts"]["zabbixvms-service"] == "zabbixvms.service:main"


def test_tray_entry_point_starts_without_a_console(pyproject):
    """UC1-R1: the tray entry point is a gui-script, so it opens no console window."""
    assert pyproject["project"]["gui-scripts"]["zabbixvms-tray"] == "zabbixvms.tray:main"
    assert "zabbixvms-tray" not in pyproject["project"].get("scripts", {})


def test_entry_points_exist_in_the_package():
    """UC1-R1: both entry points the distribution declares are really there.

    They are not called here: the service entry point is a command line of its own
    (tests/test_service.py covers what its commands do).
    """
    from zabbixvms import service, tray

    assert callable(service.main)
    assert callable(tray.main)


def test_package_data_carries_the_default_configuration(pyproject):
    """UC2-R7: the default configuration is shipped inside the package."""
    patterns = pyproject["tool"]["setuptools"]["package-data"]["zabbixvms"]

    assert "data/*.json" in patterns


def test_the_version_has_a_single_home(pyproject):
    """The version lives in the package only, so two places cannot drift apart."""
    assert "version" not in pyproject["project"], "pyproject must not carry its own version"
    assert "version" in pyproject["project"]["dynamic"]
    assert pyproject["tool"]["setuptools"]["dynamic"]["version"] == {
        "attr": "zabbixvms.__version__"
    }


def test_the_version_looks_like_a_release_number():
    """Every change that reaches a server raises it, so that pip sees an upgrade."""
    import zabbixvms

    parts = zabbixvms.__version__.split(".")

    assert len(parts) == 3, zabbixvms.__version__
    assert all(part.isdigit() for part in parts), zabbixvms.__version__


def test_the_offline_installer_calls_things_what_the_code_calls_them():
    """The script shipped with the wheels drives the service, so the names must match."""
    from zabbixvms import service

    script = INSTALLER.read_text(encoding="utf-8-sig")

    assert f"$ServiceName = '{service.SERVICE_NAME}'" in script
    assert "$PackageName = 'zabbixvms'" in script
    assert "zabbixvms-service.exe" in script


def test_the_offline_installer_is_readable_by_windows_powershell():
    """Without the byte order mark PowerShell 5.1 mangles the Czech messages."""
    assert INSTALLER.read_bytes().startswith(b"\xef\xbb\xbf")
