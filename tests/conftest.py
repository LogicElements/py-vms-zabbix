"""Keeps the tests away from the machine they run on.

Both of these bit once: a test run wrote 48 entries into the real Windows Event Log
under the source of the agent, mixed in among the entries of the service that was
really running. Nothing in a test may reach the event log or the real ProgramData.
"""

import pytest
import win32evtlogutil


@pytest.fixture(autouse=True)
def away_from_the_machine(monkeypatch, tmp_path):
    """Point ProgramData at a temporary folder and swallow event log writes.

    A test that is about the event log patches ReportEvent itself; that patch is
    applied after this one and wins.
    """
    monkeypatch.setenv("ProgramData", str(tmp_path / "ProgramData"))
    monkeypatch.setattr(win32evtlogutil, "ReportEvent", lambda *args, **kwargs: None)
