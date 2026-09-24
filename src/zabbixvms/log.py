"""Where the agent writes what happened: a rotating log file next to the
configuration, and the Windows Event Log for the few events that matter.

Both the service and the tray application write to the same file. Each record is
written with a stream that is opened and closed again, so neither process holds the
file open; that keeps the appends whole and lets whichever process fills the file
rotate it.
"""

from __future__ import annotations

import logging
import msvcrt
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import win32evtlog
import win32evtlogutil

from zabbixvms.config import data_folder

LOG_FILENAME = "zabbixvms.log"

# One megabyte per file and five kept files, so the logs cannot grow without end.
MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 5

# Timestamp, level and the text of the event.
RECORD_FORMAT = "%(asctime)s %(levelname)s %(message)s"

# Source the events appear under in the Event Viewer.
EVENT_SOURCE = "ZabbixVms"
EVENT_ID = 1

log = logging.getLogger("zabbixvms")


def log_path() -> Path:
    """The log file lives in the same folder as the configuration."""
    return data_folder() / LOG_FILENAME


class SharedRotatingFileHandler(RotatingFileHandler):
    """Rotating handler two processes can write to at the same time.

    Opening the file in append mode is not enough on Windows: the C runtime turns an
    append into a seek to the end followed by a write, and two processes doing that
    at once overwrite each other's records. Every record is therefore written under
    an exclusive lock on the first byte of the file, and the file is held open only
    for as long as that takes, so whoever fills it up can also rotate it.
    """

    def __init__(self, filename, **kwargs) -> None:
        super().__init__(filename, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
                         encoding="utf-8", delay=True, **kwargs)

    def emit(self, record) -> None:
        try:
            data = (self.format(record) + self.terminator).encode("utf-8")
            size = self._append_under_lock(data)
            if self.maxBytes and size >= self.maxBytes:
                self.doRollover()
        except Exception:
            self.handleError(record)

    def _append_under_lock(self, data: bytes) -> int:
        """Append one record while no other process writes; return the new size."""
        with open(self.baseFilename, "ab") as stream:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                stream.seek(0, os.SEEK_END)
                stream.write(data)
                stream.flush()
                return stream.tell()
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except OSError:
            # The other process holds the file right now and will rotate it itself.
            pass


def setup(path: os.PathLike | str | None = None, level: int = logging.INFO) -> Path:
    """Send the log of the package to the file, and return where it went."""
    path = Path(path) if path is not None else log_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    for handler in list(log.handlers):
        log.removeHandler(handler)
        handler.close()

    handler = SharedRotatingFileHandler(path)
    handler.setFormatter(logging.Formatter(RECORD_FORMAT))
    log.addHandler(handler)
    log.setLevel(level)
    # The records belong in the file, not in whatever the root logger does.
    log.propagate = False
    return path


def report_event(message: str, error: bool = False) -> None:
    """Put one event into the Windows Event Log under the source of the agent.

    Only the few events UC5-R2 asks for go here; everything else stays in the file.
    Failing to write an event must never bring the agent down, so it is only logged.
    """
    event_type = (win32evtlog.EVENTLOG_ERROR_TYPE if error
                  else win32evtlog.EVENTLOG_INFORMATION_TYPE)
    try:
        win32evtlogutil.ReportEvent(EVENT_SOURCE, EVENT_ID, eventType=event_type,
                                    strings=[message])
    except Exception as err:
        log.warning("event %r could not be written to the event log: %s", message, err)


def register_event_source() -> None:
    """Make the source known, so the events read as text instead of a complaint."""
    win32evtlogutil.AddSourceToRegistry(EVENT_SOURCE)


def unregister_event_source() -> None:
    """Take the source away again when the agent is unregistered."""
    try:
        win32evtlogutil.RemoveSourceFromRegistry(EVENT_SOURCE)
    except Exception:
        # Nothing registered; unregistering twice is not an error.
        pass
