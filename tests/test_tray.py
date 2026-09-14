"""Tests of the tray application against faked objects: the colour of the icon, what
the menu items do and which file Otevřít konfiguraci opens
(UC1-R5, UC1-R6, UC2-R8)."""

import win32service

from zabbixvms import tray as tray_module
from zabbixvms.config import config_path
from zabbixvms.tray import (
    MENU,
    POLL_INTERVAL,
    RUNNING_COLOR,
    STOPPED_COLOR,
    TrayApp,
    icon_color,
)


class FakeController:
    def __init__(self, state=win32service.SERVICE_STOPPED):
        self._state = state
        self.calls = []

    def state(self):
        return self._state

    def set_state(self, state):
        self._state = state

    def start(self):
        self.calls.append("start")
        self._state = win32service.SERVICE_RUNNING

    def stop(self):
        self.calls.append("stop")
        self._state = win32service.SERVICE_STOPPED

    def restart(self):
        self.calls.append("restart")
        self._state = win32service.SERVICE_RUNNING


class FakeIcon:
    def __init__(self):
        self.colors = []

    def set_color(self, color):
        self.colors.append(color)


def make_app(state=win32service.SERVICE_STOPPED):
    controller = FakeController(state)
    icon = FakeIcon()
    opened = []
    app = TrayApp(controller=controller, icon=icon, open_file=opened.append)
    return app, controller, icon, opened


def test_running_service_has_its_own_colour():
    """UC1-R5: one colour means the service runs."""
    assert icon_color(win32service.SERVICE_RUNNING) == RUNNING_COLOR


def test_stopped_service_has_a_different_colour():
    """UC1-R5: a service that is not running is a different colour."""
    assert icon_color(win32service.SERVICE_STOPPED) == STOPPED_COLOR
    assert RUNNING_COLOR != STOPPED_COLOR


def test_pending_and_missing_service_count_as_not_running():
    """Starting, stopping and a service that is not installed are not running."""
    for state in (win32service.SERVICE_START_PENDING,
                  win32service.SERVICE_STOP_PENDING,
                  win32service.SERVICE_PAUSED,
                  None):
        assert icon_color(state) == STOPPED_COLOR


def test_first_poll_paints_the_icon():
    app, _, icon, _ = make_app(win32service.SERVICE_RUNNING)

    app.poll()

    assert icon.colors == [RUNNING_COLOR]


def test_poll_repaints_only_when_the_state_changed():
    """UC1-R5: the state is asked for repeatedly, the icon changes when it changes."""
    app, controller, icon, _ = make_app(win32service.SERVICE_STOPPED)
    app.poll()
    app.poll()

    controller.set_state(win32service.SERVICE_RUNNING)
    app.poll()
    app.poll()

    assert icon.colors == [STOPPED_COLOR, RUNNING_COLOR]


def test_state_is_asked_for_every_five_seconds():
    """UC1-R5: the period is five seconds, so a change shows within five seconds."""
    assert POLL_INTERVAL == 5


def test_menu_has_the_four_items():
    """UC1-R6, UC2-R8: the context menu holds exactly these items, in this order."""
    app, _, _, _ = make_app()

    assert app.menu_labels == ("Spustit", "Zastavit", "Restartovat",
                               "Otevřít konfiguraci")


def test_start_item_starts_the_service():
    """UC1-R6: Spustit starts the service."""
    app, controller, _, _ = make_app(win32service.SERVICE_STOPPED)

    app.invoke(0)

    assert controller.calls == ["start"]


def test_stop_item_stops_the_service():
    """UC1-R6: Zastavit stops the service."""
    app, controller, _, _ = make_app(win32service.SERVICE_RUNNING)

    app.invoke(1)

    assert controller.calls == ["stop"]


def test_restart_item_restarts_the_service():
    """UC1-R6: Restartovat restarts the service."""
    app, controller, _, _ = make_app(win32service.SERVICE_RUNNING)

    app.invoke(2)

    assert controller.calls == ["restart"]


def test_action_repaints_the_icon_at_once():
    """After an action the colour follows the new state without waiting for the timer."""
    app, _, icon, _ = make_app(win32service.SERVICE_STOPPED)
    app.poll()

    app.invoke(0)

    assert icon.colors == [STOPPED_COLOR, RUNNING_COLOR]


def test_configuration_item_opens_the_active_configuration():
    """UC2-R8: the item opens the configuration file from ProgramData."""
    app, _, _, opened = make_app()

    app.invoke(3)

    assert opened == [str(config_path())]


def test_every_menu_item_has_an_action():
    app, _, _, _ = make_app()

    for _, action in MENU:
        assert callable(getattr(app, action))


def test_icon_is_named_after_the_agent():
    """UC1-R5: the icon is identifiable by the name of the agent."""
    from zabbixvms.service import DISPLAY_NAME

    assert tray_module.DISPLAY_NAME == DISPLAY_NAME == "VMS zabbix agent"


def test_solid_icon_really_builds_an_icon():
    """The icon handle is built from a colour without a visible window."""
    handle = tray_module.solid_icon(RUNNING_COLOR)

    assert handle
