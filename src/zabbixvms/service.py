"""The agent as a Windows service.

The service hosts the measurement loop of agent.py. Registration sets the start type
to Automatic and grants ordinary users the right to query, start and stop the service,
but not to change its configuration or remove it.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import ntsecuritycon
import win32api
import win32con
import win32security
import win32service
import win32serviceutil

from zabbixvms import log as logging_setup
from zabbixvms.agent import Agent
from zabbixvms.config import config_path, load_config
from zabbixvms.log import log

SERVICE_NAME = "ZabbixVms"
DISPLAY_NAME = "VMS zabbix agent"
DESCRIPTION = "Sends metrics on the VMS software of the monitored turbines to Zabbix"

# The tray application starts with every user session; registering it belongs to the
# registration of the agent, so the operator sets up nothing by hand.
TRAY_COMMAND = "zabbixvms-tray"
TRAY_RUN_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
TRAY_RUN_VALUE = "ZabbixVmsTray"

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

# What ordinary users may do with the files in ProgramData: read, write and delete
# them, which is what Windows calls Modify. The service creates the configuration and
# the log as LocalSystem, and without this an ordinary user could only read them -
# the tray could not write to the log and the operator could not save a changed
# configuration.
DATA_RIGHTS = (
    ntsecuritycon.FILE_GENERIC_READ
    | ntsecuritycon.FILE_GENERIC_WRITE
    | ntsecuritycon.FILE_GENERIC_EXECUTE
    | ntsecuritycon.DELETE
)

# The entry is inherited by the folder's files and subfolders, so it also covers the
# configuration and the log that are already in there.
DATA_INHERITANCE = (ntsecuritycon.OBJECT_INHERIT_ACE
                    | ntsecuritycon.CONTAINER_INHERIT_ACE)


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
        logging_setup.setup()
        try:
            self._agent = self.build_agent()
        except Exception as err:
            message = f"service {SERVICE_NAME} cannot start: {err}"
            log.error(message)
            logging_setup.report_event(message, error=True)
            raise

        log.info("service %s started", SERVICE_NAME)
        logging_setup.report_event(f"service {SERVICE_NAME} started")
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._agent.run()

    def SvcStop(self) -> None:
        """Tell the loop to finish and report the pending stop to the SCM."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._agent is not None:
            self._agent.stop()
        log.info("service %s stopped", SERVICE_NAME)
        logging_setup.report_event(f"service {SERVICE_NAME} stopped")

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


def grant_data_access(dacl, sid=USERS_SID, rights: int = DATA_RIGHTS):
    """Add an inheritable allow entry to a folder's DACL, unless it is already in.

    Registering twice must not pile the same entry up again.
    """
    for index in range(dacl.GetAceCount()):
        (ace_type, flags), mask, ace_sid = dacl.GetAce(index)
        if (ace_type == ntsecuritycon.ACCESS_ALLOWED_ACE_TYPE and ace_sid == sid
                and mask == rights and flags & DATA_INHERITANCE == DATA_INHERITANCE):
            return dacl
    dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION, DATA_INHERITANCE,
                               rights, sid)
    return dacl


def grant_users_data_folder() -> Path:
    """Let ordinary users write the configuration and the log in ProgramData."""
    folder = config_path().parent
    folder.mkdir(parents=True, exist_ok=True)

    descriptor = win32security.GetNamedSecurityInfo(
        str(folder), win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION)
    dacl = grant_data_access(descriptor.GetSecurityDescriptorDacl())
    # SetNamedSecurityInfo, unlike SetFileSecurity, hands the inheritable entry down
    # to the files that are in the folder already.
    win32security.SetNamedSecurityInfo(
        str(folder), win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION, None, None, dacl, None)
    return folder


def tray_executable() -> str:
    """Path of the tray application's executable installed beside this one."""
    beside = Path(sys.executable).parent / f"{TRAY_COMMAND}.exe"
    if beside.exists():
        return str(beside)
    found = shutil.which(TRAY_COMMAND)
    if found is None:
        raise FileNotFoundError(
            f"{TRAY_COMMAND} was not found; is the package installed?")
    return found


def register_tray_autostart() -> None:
    """Start the tray application for every user who logs on to the machine."""
    key = win32api.RegCreateKey(win32con.HKEY_LOCAL_MACHINE, TRAY_RUN_KEY)
    try:
        win32api.RegSetValueEx(key, TRAY_RUN_VALUE, 0, win32con.REG_SZ,
                               f'"{tray_executable()}"')
    finally:
        win32api.RegCloseKey(key)


def unregister_tray_autostart() -> None:
    """Take the tray application out of the automatic start again."""
    try:
        key = win32api.RegOpenKeyEx(win32con.HKEY_LOCAL_MACHINE, TRAY_RUN_KEY, 0,
                                    win32con.KEY_SET_VALUE)
    except win32api.error:
        return
    try:
        win32api.RegDeleteValue(key, TRAY_RUN_VALUE)
    except win32api.error:
        # Nothing registered; unregistering twice is not an error.
        pass
    finally:
        win32api.RegCloseKey(key)


def install() -> None:
    """Register the service: automatic start, control for ordinary users, tray."""
    win32serviceutil.InstallService(
        pythonClassString=f"{ZabbixVmsService.__module__}.{ZabbixVmsService.__name__}",
        serviceName=SERVICE_NAME,
        displayName=DISPLAY_NAME,
        description=DESCRIPTION,
        startType=win32service.SERVICE_AUTO_START,
    )
    grant_user_control()
    grant_users_data_folder()
    register_tray_autostart()
    logging_setup.register_event_source()


def remove() -> None:
    """Unregister the service and stop starting the tray application."""
    unregister_tray_autostart()
    logging_setup.unregister_event_source()
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
