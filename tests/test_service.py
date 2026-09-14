"""Tests of the Windows service: the loop is started and stopped with the service
and the security descriptor grants ordinary users control but nothing more
(UC1-R2, UC1-R3, UC1-R7)."""

import ntsecuritycon
import pytest
import win32security
import win32service

from zabbixvms import service as service_module
from zabbixvms.service import (
    DISPLAY_NAME,
    FORBIDDEN_USER_RIGHTS,
    SERVICE_NAME,
    USER_RIGHTS,
    USERS_SID,
    ZabbixVmsService,
    allow_rights,
)


class FakeAgent:
    def __init__(self):
        self.runs = 0
        self.stops = 0
        self.running = False

    def run(self):
        self.runs += 1
        self.running = True

    def stop(self):
        self.stops += 1
        self.running = False


def make_service(agent=None, monkeypatch=None):
    """Service instance without the SCM handshake of ServiceFramework.__init__."""
    service = ZabbixVmsService.__new__(ZabbixVmsService)
    service._agent = None
    service.reported = []
    service.ReportServiceStatus = service.reported.append
    if agent is not None:
        monkeypatch.setattr(ZabbixVmsService, "build_agent", staticmethod(lambda: agent))
    return service


def test_service_is_named_the_way_the_operator_sees_it():
    """UC1-R2: the service is ZabbixVms with the display name of the agent."""
    assert ZabbixVmsService._svc_name_ == SERVICE_NAME == "ZabbixVms"
    assert ZabbixVmsService._svc_display_name_ == DISPLAY_NAME == "VMS zabbix agent"
    assert ZabbixVmsService._svc_description_


def test_run_starts_the_measurement_loop(monkeypatch):
    agent = FakeAgent()
    service = make_service(agent, monkeypatch)

    service.SvcDoRun()

    assert agent.runs == 1


def test_running_is_reported_before_the_loop(monkeypatch):
    """The SCM learns the service is running, otherwise the start times out."""
    agent = FakeAgent()
    service = make_service(agent, monkeypatch)

    service.SvcDoRun()

    assert win32service.SERVICE_RUNNING in service.reported


def test_stop_ends_the_measurement_loop(monkeypatch):
    agent = FakeAgent()
    service = make_service(agent, monkeypatch)
    service.SvcDoRun()

    service.SvcStop()

    assert agent.stops == 1
    assert not agent.running


def test_stop_reports_the_pending_stop(monkeypatch):
    agent = FakeAgent()
    service = make_service(agent, monkeypatch)
    service.SvcDoRun()

    service.SvcStop()

    assert service.reported[-1] == win32service.SERVICE_STOP_PENDING


def test_stop_before_the_loop_started_is_harmless():
    service = make_service()

    service.SvcStop()

    assert service.reported == [win32service.SERVICE_STOP_PENDING]


def test_bad_configuration_stops_the_service_from_starting(monkeypatch):
    """A configuration the agent cannot work with fails the start, it does not
    leave a service that runs and reports nothing."""
    from zabbixvms.config import ConfigError

    def build_agent():
        raise ConfigError("five turbines")

    monkeypatch.setattr(ZabbixVmsService, "build_agent", staticmethod(build_agent))
    service = make_service()

    with pytest.raises(ConfigError):
        service.SvcDoRun()

    assert win32service.SERVICE_RUNNING not in service.reported


def test_user_rights_allow_query_start_and_stop():
    """UC1-R7: an ordinary user may ask about the service, start it and stop it."""
    for right in (win32service.SERVICE_QUERY_STATUS, win32service.SERVICE_START,
                  win32service.SERVICE_STOP):
        assert USER_RIGHTS & right


def test_user_rights_do_not_allow_reconfiguring_or_removing():
    """UC1-R7: the same user may not unregister the service or change it."""
    assert not USER_RIGHTS & FORBIDDEN_USER_RIGHTS
    assert not USER_RIGHTS & win32service.SERVICE_CHANGE_CONFIG
    assert not USER_RIGHTS & ntsecuritycon.DELETE


def test_descriptor_is_built_from_the_required_rights():
    """UC1-R7: the descriptor carries one entry for users with exactly those rights."""
    descriptor = win32security.SECURITY_DESCRIPTOR()

    allow_rights(descriptor, USERS_SID, USER_RIGHTS)

    dacl = descriptor.GetSecurityDescriptorDacl()
    assert dacl.GetAceCount() == 1
    (ace_type, _flags), mask, sid = dacl.GetAce(0)
    assert ace_type == ntsecuritycon.ACCESS_ALLOWED_ACE_TYPE
    assert mask == USER_RIGHTS
    assert sid == USERS_SID


def test_descriptor_keeps_the_entries_it_already_had():
    """The rights of Administrators and SYSTEM are not replaced but added to."""
    descriptor = win32security.SECURITY_DESCRIPTOR()
    admins = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid)
    allow_rights(descriptor, admins, win32service.SERVICE_ALL_ACCESS)

    allow_rights(descriptor, USERS_SID, USER_RIGHTS)

    dacl = descriptor.GetSecurityDescriptorDacl()
    assert dacl.GetAceCount() == 2
    assert dacl.GetAce(0)[2] == admins


def test_users_sid_is_the_builtin_users_group():
    assert win32security.ConvertSidToStringSid(USERS_SID) == "S-1-5-32-545"


def test_install_registers_with_automatic_start(monkeypatch):
    """UC1-R3: the registered service starts with the system."""
    captured = {}
    monkeypatch.setattr(service_module.win32serviceutil, "InstallService",
                        lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(service_module, "grant_user_control", lambda: None)
    monkeypatch.setattr(service_module, "register_tray_autostart", lambda: None)

    service_module.install()

    assert captured["serviceName"] == SERVICE_NAME
    assert captured["displayName"] == DISPLAY_NAME
    assert captured["startType"] == win32service.SERVICE_AUTO_START
    assert captured["pythonClassString"] == "zabbixvms.service.ZabbixVmsService"


def test_install_grants_the_rights_of_ordinary_users(monkeypatch):
    """UC1-R7: the rights are set as part of the registration, not by hand."""
    granted = []
    monkeypatch.setattr(service_module.win32serviceutil, "InstallService",
                        lambda **kwargs: None)
    monkeypatch.setattr(service_module, "grant_user_control",
                        lambda: granted.append(True))
    monkeypatch.setattr(service_module, "register_tray_autostart", lambda: None)

    service_module.install()

    assert granted == [True]


def test_remove_unregisters_the_service(monkeypatch):
    """UC1-R2: there is a command that takes the service away again."""
    removed = []
    monkeypatch.setattr(service_module.win32serviceutil, "RemoveService",
                        removed.append)
    monkeypatch.setattr(service_module, "unregister_tray_autostart", lambda: None)

    service_module.remove()

    assert removed == [SERVICE_NAME]


def test_install_registers_the_tray_for_automatic_start(monkeypatch):
    """UC1-R8: the automatic start of the tray is set up by the installation."""
    registered = []
    monkeypatch.setattr(service_module.win32serviceutil, "InstallService",
                        lambda **kwargs: None)
    monkeypatch.setattr(service_module, "grant_user_control", lambda: None)
    monkeypatch.setattr(service_module, "register_tray_autostart",
                        lambda: registered.append(True))

    service_module.install()

    assert registered == [True]


def test_remove_takes_the_tray_out_of_automatic_start(monkeypatch):
    """Unregistering the agent leaves no entry pointing at a missing command."""
    unregistered = []
    monkeypatch.setattr(service_module.win32serviceutil, "RemoveService",
                        lambda name: None)
    monkeypatch.setattr(service_module, "unregister_tray_autostart",
                        lambda: unregistered.append(True))

    service_module.remove()

    assert unregistered == [True]


def test_autostart_is_registered_for_every_user_of_the_machine():
    """UC1-R8: the entry is machine-wide, so it works for whoever logs on."""
    assert service_module.TRAY_RUN_KEY == \
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
    assert service_module.TRAY_COMMAND == "zabbixvms-tray"


def test_tray_executable_is_taken_from_beside_the_running_interpreter(monkeypatch, tmp_path):
    """The tray executable installed by the same package is the one registered."""
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    (scripts / "zabbixvms-tray.exe").write_bytes(b"")
    monkeypatch.setattr(service_module.sys, "executable", str(scripts / "python.exe"))

    assert service_module.tray_executable() == str(scripts / "zabbixvms-tray.exe")


def test_missing_tray_executable_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(service_module.sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(service_module.shutil, "which", lambda command: None)

    with pytest.raises(FileNotFoundError):
        service_module.tray_executable()


@pytest.mark.parametrize("command, expected", [("install", "install"), ("remove", "remove")])
def test_main_handles_registration_itself(monkeypatch, command, expected):
    called = []
    monkeypatch.setattr(service_module, "install", lambda: called.append("install"))
    monkeypatch.setattr(service_module, "remove", lambda: called.append("remove"))

    service_module.main(["zabbixvms-service", command])

    assert called == [expected]


def test_main_leaves_the_other_commands_to_pywin32(monkeypatch):
    handled = []
    monkeypatch.setattr(service_module.win32serviceutil, "HandleCommandLine",
                        lambda cls, argv=None: handled.append((cls, argv)))

    service_module.main(["zabbixvms-service", "start"])

    assert handled == [(ZabbixVmsService, ["zabbixvms-service", "start"])]
