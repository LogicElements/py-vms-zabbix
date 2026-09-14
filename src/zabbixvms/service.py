"""The agent as a Windows service.

The service hosts the measurement loop of agent.py. Registration sets the start type
to Automatic and grants ordinary users the right to query, start and stop the service,
but not to change its configuration or remove it.
"""

from __future__ import annotations

import sys

import ntsecuritycon
import win32security
import win32service
import win32serviceutil

from zabbixvms.agent import Agent
from zabbixvms.config import load_config

SERVICE_NAME = "ZabbixVms"
DISPLAY_NAME = "VMS zabbix agent"
DESCRIPTION = "Sends metrics on the VMS software of the monitored turbines to Zabbix"

# Everyone on the machine, which is what "a user without administrator rights" means.
USERS_SID = win32security.CreateWellKnownSid(win32security.WinBuiltinUsersSid)

# What such a user may do with the service: look at it, start it and stop it. The
# rights to reconfigure or delete the service are deliberately not among them, so a
# non-administrator cannot unregister the service or repoint it elsewhere.
USER_RIGHTS = (
    win32service.SERVICE_QUERY_CONFIG
    | win32service.SERVICE_QUERY_STATUS
    | win32service.SERVICE_ENUMERATE_DEPENDENTS
    | win32service.SERVICE_INTERROGATE
    | win32service.SERVICE_USER_DEFINED_CONTROL
    | win32service.SERVICE_START
    | win32service.SERVICE_STOP
    | ntsecuritycon.READ_CONTROL
)

# Rights a user without administrator rights must not gain over the service.
FORBIDDEN_USER_RIGHTS = (
    win32service.SERVICE_CHANGE_CONFIG
    | ntsecuritycon.DELETE
    | ntsecuritycon.WRITE_DAC
    | ntsecuritycon.WRITE_OWNER
)


class ZabbixVmsService(win32serviceutil.ServiceFramework):
    """Service framework wrapper around the measurement loop."""

    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = DISPLAY_NAME
    _svc_description_ = DESCRIPTION

    def __init__(self, args) -> None:
        super().__init__(args)
        self._agent = None

    def SvcDoRun(self) -> None:
        """Run the measurement loop until the service is asked to stop.

        An unusable configuration ends the service here, so a wrong setting is seen
        as a service that refuses to start instead of one that runs and reports
        nothing.
        """
        self._agent = self.build_agent()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._agent.run()

    def SvcStop(self) -> None:
        """Tell the loop to finish and report the pending stop to the SCM."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._agent is not None:
            self._agent.stop()

    @staticmethod
    def build_agent() -> Agent:
        """Agent built from the active configuration in ProgramData."""
        return Agent(load_config())


def allow_rights(descriptor, sid, rights: int):
    """Add one allow entry for the given rights to the descriptor's DACL."""
    dacl = descriptor.GetSecurityDescriptorDacl()
    if dacl is None:
        dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, rights, sid)
    descriptor.SetSecurityDescriptorDacl(1, dacl, 0)
    return descriptor


def grant_user_control(service_name: str = SERVICE_NAME) -> None:
    """Let users without administrator rights query, start and stop the service.

    The rights are added to the security descriptor the service already has, so the
    entries of Administrators and SYSTEM stay as they are.
    """
    manager = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        access = ntsecuritycon.READ_CONTROL | ntsecuritycon.WRITE_DAC
        handle = win32service.OpenService(manager, service_name, access)
        try:
            descriptor = win32service.QueryServiceObjectSecurity(
                handle, win32security.DACL_SECURITY_INFORMATION)
            allow_rights(descriptor, USERS_SID, USER_RIGHTS)
            win32service.SetServiceObjectSecurity(
                handle, win32security.DACL_SECURITY_INFORMATION, descriptor)
        finally:
            win32service.CloseServiceHandle(handle)
    finally:
        win32service.CloseServiceHandle(manager)


def install() -> None:
    """Register the service: automatic start and control for ordinary users."""
    win32serviceutil.InstallService(
        pythonClassString=f"{ZabbixVmsService.__module__}.{ZabbixVmsService.__name__}",
        serviceName=SERVICE_NAME,
        displayName=DISPLAY_NAME,
        description=DESCRIPTION,
        startType=win32service.SERVICE_AUTO_START,
    )
    grant_user_control()


def remove() -> None:
    """Unregister the service."""
    win32serviceutil.RemoveService(SERVICE_NAME)


def main(argv=None) -> None:
    """Entry point of the zabbixvms-service command.

    install and remove are handled here so that the automatic start and the rights of
    ordinary users are set without the operator passing anything extra; the remaining
    commands (start, stop, restart, debug) are left to pywin32.
    """
    argv = list(sys.argv if argv is None else argv)
    command = argv[1] if len(argv) > 1 else ""

    if command == "install":
        install()
    elif command == "remove":
        remove()
    else:
        win32serviceutil.HandleCommandLine(ZabbixVmsService, argv=argv)
