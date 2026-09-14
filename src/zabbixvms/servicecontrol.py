"""Asking the service control manager about the ZabbixVms service and controlling it.

Only the rights an ordinary user was granted at registration are used - query, start
and stop - so the tray application needs no elevation.
"""

from __future__ import annotations

import time

import win32service

from zabbixvms.service import SERVICE_NAME

# Returned by state() when there is no such service.
NOT_INSTALLED = None

# How long restart() waits for the service to come to a stop.
STOP_TIMEOUT = 30.0
POLL_STEP = 0.2


class ServiceControlError(Exception):
    """The service could not be started or stopped."""


class ServiceController:
    """Reads the state of the service and starts, stops and restarts it."""

    def __init__(self, service_name: str = SERVICE_NAME, api=win32service,
                 sleep=time.sleep) -> None:
        self._service_name = service_name
        self._api = api
        self._sleep = sleep

    def state(self):
        """Current state of the service, or NOT_INSTALLED when there is none."""
        try:
            return self._query(self._api.SERVICE_QUERY_STATUS,
                               lambda handle: self._api.QueryServiceStatus(handle)[1])
        except self._api.error:
            # The service is not registered, or this user may not even look at it.
            return NOT_INSTALLED

    def is_running(self) -> bool:
        return self.state() == self._api.SERVICE_RUNNING

    def start(self) -> None:
        """Start the service."""
        try:
            self._query(self._api.SERVICE_START,
                        lambda handle: self._api.StartService(handle, None))
        except self._api.error as err:
            raise ServiceControlError(
                f"service {self._service_name} could not be started: {err}") from err

    def stop(self) -> None:
        """Stop the service."""
        try:
            self._query(self._api.SERVICE_STOP,
                        lambda handle: self._api.ControlService(
                            handle, self._api.SERVICE_CONTROL_STOP))
        except self._api.error as err:
            raise ServiceControlError(
                f"service {self._service_name} could not be stopped: {err}") from err

    def restart(self) -> None:
        """Stop the service, wait until it really stopped, and start it again."""
        self.stop()
        self._wait_until_stopped()
        self.start()

    def _wait_until_stopped(self) -> None:
        deadline = STOP_TIMEOUT
        while deadline > 0:
            if self.state() in (self._api.SERVICE_STOPPED, NOT_INSTALLED):
                return
            self._sleep(POLL_STEP)
            deadline -= POLL_STEP
        raise ServiceControlError(
            f"service {self._service_name} did not stop within {STOP_TIMEOUT} s")

    def _query(self, access: int, action):
        """Run action over a service handle opened with the given access."""
        manager = self._api.OpenSCManager(None, None, self._api.SC_MANAGER_CONNECT)
        try:
            handle = self._api.OpenService(manager, self._service_name, access)
            try:
                return action(handle)
            finally:
                self._api.CloseServiceHandle(handle)
        finally:
            self._api.CloseServiceHandle(manager)
