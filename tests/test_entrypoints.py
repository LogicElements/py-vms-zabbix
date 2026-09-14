"""Tests of the package skeleton: one distribution brings both the service and
the tray application, each with its own entry point (UC1-R1)."""

import tomllib
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


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


def test_entry_points_are_callable():
    """UC1-R1: both entry points exist in the package and can be called."""
    from zabbixvms import service, tray

    assert service.main() is None
    assert tray.main() is None


def test_package_data_carries_the_default_configuration(pyproject):
    """UC2-R7: the default configuration is shipped inside the package."""
    patterns = pyproject["tool"]["setuptools"]["package-data"]["zabbixvms"]

    assert "data/*.json" in patterns
