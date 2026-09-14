"""Tests of the service control against a faked win32service: the state, the
control actions and the restart (UC1-R5, UC1-R6)."""

import pytest
import win32service

from zabbixvms.servicecontrol import (
    NOT_INSTALLED,
    ServiceControlError,
    ServiceController,
)


class FakeApi:
    """Stands in for the win32service module."""

    error = win32service.error

    SERVICE_QUERY_STATUS = win32service.SERVICE_QUERY_STATUS
    SERVICE_START = win32service.SERVICE_START
    SERVICE_STOP = win32service.SERVICE_STOP
    SERVICE_RUNNING = win32service.SERVICE_RUNNING
    SERVICE_STOPPED = win32service.SERVICE_STOPPED
    SERVICE_CONTROL_STOP = win32service.SERVICE_CONTROL_STOP
    SC_MANAGER_CONNECT = win32service.SC_MANAGER_CONNECT

    def __init__(self, states=None, open_error=None):
        # States handed out by successive queries; the last one repeats.
        self.states = list(states) if states else [win32service.SERVICE_STOPPED]
        self.open_error = open_error
        self.calls = []
        self.opened_access = []
        self.closed = 0

    def OpenSCManager(self, machine, database, access):
        return "scm"

    def OpenService(self, manager, name, access):
        self.opened_access.append(access)
        if self.open_error is not None:
            raise self.open_error
        return "service"

    def CloseServiceHandle(self, handle):
        self.closed += 1

    def QueryServiceStatus(self, handle):
        state = self.states[0] if len(self.states) == 1 else self.states.pop(0)
        return (0, state, 0, 0, 0, 0, 0)

    def StartService(self, handle, args):
        self.calls.append("StartService")

    def ControlService(self, handle, control):
        self.calls.append(("ControlService", control))


def make_controller(api=None, **kwargs):
    api = api if api is not None else FakeApi(**kwargs)
    return ServiceController("ZabbixVms", api=api, sleep=lambda seconds: None), api


def test_state_of_a_running_service():
    controller, _ = make_controller(states=[win32service.SERVICE_RUNNING])

    assert controller.state() == win32service.SERVICE_RUNNING
    assert controller.is_running()


def test_state_of_a_stopped_service():
    controller, _ = make_controller(states=[win32service.SERVICE_STOPPED])

    assert controller.state() == win32service.SERVICE_STOPPED
    assert not controller.is_running()


def test_missing_service_has_no_state():
    """A service that is not registered is reported as not installed, not an error."""
    error = win32service.error(1060, "OpenService", "service does not exist")
    controller, _ = make_controller(open_error=error)

    assert controller.state() is NOT_INSTALLED
    assert not controller.is_running()


def test_start_asks_the_service_control_manager():
    """UC1-R6: Spustit reaches the service control manager."""
    controller, api = make_controller()

    controller.start()

    assert "StartService" in api.calls


def test_stop_sends_the_stop_control():
    """UC1-R6: Zastavit sends the stop control code."""
    controller, api = make_controller(states=[win32service.SERVICE_RUNNING])

    controller.stop()

    assert ("ControlService", win32service.SERVICE_CONTROL_STOP) in api.calls


def test_restart_stops_before_it_starts():
    """UC1-R6: Restartovat stops the service and starts it again, in that order."""
    controller, api = make_controller(
        states=[win32service.SERVICE_RUNNING, win32service.SERVICE_STOPPED])

    controller.restart()

    actions = [call if isinstance(call, str) else call[0] for call in api.calls]
    assert actions == ["ControlService", "StartService"]


def test_restart_waits_until_the_service_stopped():
    """The service is started again only once it really came to a stop."""
    controller, api = make_controller(states=[
        win32service.SERVICE_RUNNING,
        win32service.SERVICE_STOP_PENDING,
        win32service.SERVICE_STOPPED,
    ])

    controller.restart()

    assert api.calls[-1] == "StartService"


def test_restart_gives_up_when_the_service_will_not_stop():
    controller, _ = make_controller(states=[win32service.SERVICE_RUNNING])

    with pytest.raises(ServiceControlError):
        controller.restart()


def test_start_failure_is_reported():
    error = win32service.error(5, "OpenService", "access denied")
    controller, _ = make_controller(open_error=error)

    with pytest.raises(ServiceControlError):
        controller.start()


def test_only_the_rights_of_an_ordinary_user_are_asked_for():
    """UC1-R7: query, start and stop; nothing that needs administrator rights."""
    controller, api = make_controller(states=[win32service.SERVICE_RUNNING])

    controller.state()
    controller.start()
    controller.stop()

    assert set(api.opened_access) == {win32service.SERVICE_QUERY_STATUS,
                                      win32service.SERVICE_START,
                                      win32service.SERVICE_STOP}


def test_handles_are_always_closed():
    controller, api = make_controller()

    controller.state()

    assert api.closed == 2
