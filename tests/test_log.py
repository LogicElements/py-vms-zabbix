"""Tests of the log file: where it is, what a record looks like, that it rotates
and that two processes can write to it (UC5-R1, UC5-R2)."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from zabbixvms import log as log_module
from zabbixvms.log import BACKUP_COUNT, LOG_FILENAME, MAX_BYTES, log, log_path


@pytest.fixture
def log_file(tmp_path):
    """Send the log of the package to a file of its own for one test."""
    path = log_module.setup(tmp_path / LOG_FILENAME)
    yield path
    for handler in list(log.handlers):
        log.removeHandler(handler)
        handler.close()


def test_log_lives_beside_the_configuration(monkeypatch, tmp_path):
    """UC5-R1: the log file is in the folder of the configuration."""
    monkeypatch.setenv("ProgramData", str(tmp_path))

    assert log_path() == tmp_path / "LogicElements" / "ZabbixVms" / LOG_FILENAME


def test_setup_creates_the_folder(tmp_path):
    """The first start writes the log even when nothing created the folder yet."""
    path = log_module.setup(tmp_path / "chybi" / LOG_FILENAME)
    try:
        log.info("ahoj")
    finally:
        for handler in list(log.handlers):
            log.removeHandler(handler)
            handler.close()

    assert path.exists()


def test_record_holds_time_level_and_text(log_file):
    """UC5-R1: every record has a timestamp, a level and the text."""
    log.warning("něco se nepovedlo")

    record = log_file.read_text(encoding="utf-8").strip()
    assert "WARNING" in record
    assert "něco se nepovedlo" in record
    # The timestamp of logging starts with the year.
    assert record[:2] == "20"


def test_records_of_both_levels_are_kept(log_file):
    log.info("provozní událost")
    log.error("chyba")

    text = log_file.read_text(encoding="utf-8")
    assert "provozní událost" in text
    assert "chyba" in text


def test_log_rotates_when_it_fills_up(log_file):
    """UC5-R1: the file rotates at one megabyte and five files are kept."""
    assert MAX_BYTES == 1024 * 1024
    assert BACKUP_COUNT == 5

    # A megabyte of records would be slow; the limit is lowered for the test.
    handler = log.handlers[0]
    handler.maxBytes = 200
    for index in range(50):
        log.info("záznam číslo %d, dost dlouhý na to, aby soubor narostl", index)

    rotated = sorted(log_file.parent.glob(f"{LOG_FILENAME}*"))
    assert len(rotated) > 1
    assert len(rotated) <= BACKUP_COUNT + 1


def test_handler_does_not_hold_the_file_open(log_file):
    """UC5-R1: the file is not held open, so the other process can rotate it."""
    log.info("první")

    assert log.handlers[0].stream is None


def test_two_processes_write_into_the_same_log(tmp_path):
    """UC5-R1: the service and the tray write together without spoiling records."""
    path = tmp_path / LOG_FILENAME
    source = Path(__file__).resolve().parent.parent / "src"
    script = (
        "import sys;"
        f"sys.path.insert(0, {str(source)!r});"
        "from zabbixvms import log as m;"
        f"m.setup({str(path)!r});"
        "[m.log.info('%s záznam %d', sys.argv[1], i) for i in range(30)]"
    )

    processes = [subprocess.Popen([sys.executable, "-c", script, name],
                                  stderr=subprocess.PIPE, text=True)
                 for name in ("sluzba", "tray")]
    for process in processes:
        errors = process.communicate(timeout=60)[1]
        assert process.returncode == 0
        # A handler that cannot write says so on stderr instead of raising.
        assert errors == "", errors

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) == 60
    assert sum("sluzba" in line for line in lines) == 30
    assert sum("tray" in line for line in lines) == 30
    # Every record is whole: it starts with a timestamp and holds exactly one level.
    assert all(line[:2] == "20" and line.count("INFO") == 1 for line in lines)


def test_event_is_reported_under_the_source_of_the_agent(monkeypatch):
    """UC5-R2: events appear under the source ZabbixVms."""
    import win32evtlog

    captured = {}
    monkeypatch.setattr(log_module.win32evtlogutil, "ReportEvent",
                        lambda app, event_id, eventType=None, strings=None:
                        captured.update(app=app, type=eventType, strings=strings))

    log_module.report_event("služba byla spuštěna")

    assert captured["app"] == "ZabbixVms"
    assert captured["type"] == win32evtlog.EVENTLOG_INFORMATION_TYPE
    assert captured["strings"] == ["služba byla spuštěna"]


def test_error_event_has_the_error_type(monkeypatch):
    """UC5-R2: an error that stops the agent is written as type Error."""
    import win32evtlog

    captured = {}
    monkeypatch.setattr(log_module.win32evtlogutil, "ReportEvent",
                        lambda app, event_id, eventType=None, strings=None:
                        captured.update(type=eventType))

    log_module.report_event("konfigurace je neplatná", error=True)

    assert captured["type"] == win32evtlog.EVENTLOG_ERROR_TYPE


def test_a_broken_event_log_does_not_stop_the_agent(monkeypatch, log_file):
    """Writing an event must never be what brings the agent down."""
    def fail(*args, **kwargs):
        raise OSError("event log is away")

    monkeypatch.setattr(log_module.win32evtlogutil, "ReportEvent", fail)

    log_module.report_event("cokoli")

    assert "event log is away" in log_file.read_text(encoding="utf-8")


def test_setup_replaces_earlier_handlers(tmp_path):
    """Calling setup twice must not write every record twice."""
    log_module.setup(tmp_path / "prvni.log")
    second = log_module.setup(tmp_path / "druhy.log")
    try:
        log.info("jen jednou")
    finally:
        for handler in list(log.handlers):
            log.removeHandler(handler)
            handler.close()

    assert len(second.read_text(encoding="utf-8").splitlines()) == 1
    assert not (tmp_path / "prvni.log").exists()


def test_package_log_does_not_leak_into_the_root_logger(log_file):
    assert log.propagate is False
    assert log.level == logging.INFO
