"""Systray icon showing whether the service runs, with a menu to control it.

The colour of the icon says whether the service is running, the state is asked for
every five seconds and the menu starts, stops and restarts the service and opens the
configuration. Everything runs unelevated: the rights the service grants ordinary
users at registration are enough.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32service
import win32ui

from zabbixvms.config import config_path
from zabbixvms.service import DISPLAY_NAME
from zabbixvms.servicecontrol import ServiceController

# This build of pywin32 exposes neither SetTimer nor KillTimer, so they are taken
# from user32 directly. The argument types are spelled out, otherwise the window
# handle is truncated on 64 bit.
_user32 = ctypes.windll.user32
_user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.UINT,
                             ctypes.c_void_p]
_user32.SetTimer.restype = ctypes.c_void_p
_user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_void_p]
_user32.KillTimer.restype = wintypes.BOOL

# How often the state of the service is asked for, in seconds.
POLL_INTERVAL = 5

RUNNING_COLOR = (0, 176, 80)
STOPPED_COLOR = (208, 48, 48)

ICON_SIZE = 16

# Items of the context menu, in order, each with the method that carries it out.
MENU = (
    ("Spustit", "start_service"),
    ("Zastavit", "stop_service"),
    ("Restartovat", "restart_service"),
    ("Otevřít konfiguraci", "open_configuration"),
)

# Window message the shell sends for mouse actions on the icon.
WM_TRAYICON = win32con.WM_USER + 20
TIMER_ID = 1


def icon_color(state) -> tuple[int, int, int]:
    """Colour of the icon for a state of the service.

    One colour means running; anything else - stopped, starting, stopping, or no
    such service at all - means it is not running.
    """
    if state == win32service.SERVICE_RUNNING:
        return RUNNING_COLOR
    return STOPPED_COLOR


class TrayApp:
    """The logic behind the icon: what colour it has and what the menu does."""

    def __init__(self, controller: ServiceController | None = None, icon=None,
                 open_file=os.startfile) -> None:
        self._controller = controller if controller is not None else ServiceController()
        self._icon = icon
        self._open_file = open_file
        self._state = _UNKNOWN

    @property
    def menu_labels(self) -> tuple[str, ...]:
        return tuple(label for label, _ in MENU)

    def poll(self) -> None:
        """Ask for the state and repaint the icon when it changed."""
        state = self._controller.state()
        if state == self._state:
            return
        self._state = state
        if self._icon is not None:
            self._icon.set_color(icon_color(state))

    def invoke(self, index: int) -> None:
        """Carry out the menu item of the given index."""
        getattr(self, MENU[index][1])()

    def start_service(self) -> None:
        self._controller.start()
        self.poll()

    def stop_service(self) -> None:
        self._controller.stop()
        self.poll()

    def restart_service(self) -> None:
        self._controller.restart()
        self.poll()

    def open_configuration(self) -> None:
        """Open the active configuration in whatever the system opens .json with."""
        self._open_file(str(config_path()))

    def run(self) -> None:
        """Show the icon and serve it until the user quits."""
        self._icon = TrayIcon(DISPLAY_NAME, self)
        try:
            self.poll()
            self._icon.pump()
        finally:
            self._icon.remove()


class _Unknown:
    """State before the first poll; it equals nothing, so the first poll paints."""

    def __repr__(self) -> str:
        return "<neznámý stav>"


_UNKNOWN = _Unknown()


def solid_icon(color: tuple[int, int, int], size: int = ICON_SIZE):
    """Handle of a square icon filled with one colour."""
    screen = win32gui.GetDC(0)
    screen_dc = win32ui.CreateDCFromHandle(screen)
    try:
        memory_dc = screen_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(screen_dc, size, size)
        memory_dc.SelectObject(bitmap)
        brush = win32ui.CreateBrush(win32con.BS_SOLID, win32api.RGB(*color), 0)
        memory_dc.FillRect((0, 0, size, size), brush)

        # A monochrome mask of zeros keeps the whole square opaque.
        mask = win32gui.CreateBitmap(size, size, 1, 1, None)

        return win32gui.CreateIconIndirect((0, 0, 0, mask, bitmap.GetHandle()))
    finally:
        win32gui.ReleaseDC(0, screen)


class TrayIcon:
    """The icon itself: a hidden window, the shell notification and the menu."""

    def __init__(self, tooltip: str, app: TrayApp) -> None:
        self._tooltip = tooltip
        self._app = app
        self._icon_handle = None
        self._atom = None
        self._instance = win32api.GetModuleHandle(None)
        self._window = self._create_window()
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, self._notify_data(
            solid_icon(STOPPED_COLOR)))
        _user32.SetTimer(self._window, TIMER_ID, POLL_INTERVAL * 1000, None)

    def set_color(self, color: tuple[int, int, int]) -> None:
        """Repaint the icon in the given colour."""
        win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY,
                                  self._notify_data(solid_icon(color)))

    def remove(self) -> None:
        """Take the icon out of the systray and give up the window behind it.

        The window class is unregistered too, otherwise a second icon in the same
        process would fail to register it again.
        """
        _user32.KillTimer(self._window, TIMER_ID)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self._window, 0))
        win32gui.DestroyWindow(self._window)
        if self._atom is not None:
            win32gui.UnregisterClass(self._atom, self._instance)
            self._atom = None

    def pump(self) -> None:
        win32gui.PumpMessages()

    def _notify_data(self, icon_handle):
        self._icon_handle = icon_handle
        return (self._window, 0,
                win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                WM_TRAYICON, icon_handle, self._tooltip)

    def _create_window(self):
        window_class = win32gui.WNDCLASS()
        window_class.hInstance = self._instance
        window_class.lpszClassName = "ZabbixVmsTray"
        window_class.lpfnWndProc = {
            win32con.WM_COMMAND: self._on_command,
            win32con.WM_TIMER: self._on_timer,
            win32con.WM_DESTROY: self._on_destroy,
            WM_TRAYICON: self._on_tray,
        }
        self._atom = win32gui.RegisterClass(window_class)
        return win32gui.CreateWindow(self._atom, self._tooltip, win32con.WS_OVERLAPPED,
                                     0, 0, 0, 0, 0, 0, self._instance, None)

    def _on_timer(self, window, message, wparam, lparam):
        self._app.poll()
        return 0

    def _on_command(self, window, message, wparam, lparam):
        self._app.invoke(win32api.LOWORD(wparam) - 1)
        return 0

    def _on_destroy(self, window, message, wparam, lparam):
        win32gui.PostQuitMessage(0)
        return 0

    def _on_tray(self, window, message, wparam, lparam):
        if lparam in (win32con.WM_RBUTTONUP, win32con.WM_LBUTTONUP):
            self._show_menu()
        return 0

    def _show_menu(self) -> None:
        menu = win32gui.CreatePopupMenu()
        for index, (label, _) in enumerate(MENU):
            win32gui.AppendMenu(menu, win32con.MF_STRING, index + 1, label)
        position = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self._window)
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, position[0], position[1],
                                0, self._window, None)
        win32gui.PostMessage(self._window, win32con.WM_NULL, 0, 0)


def main() -> None:
    """Entry point of the zabbixvms-tray command."""
    TrayApp().run()
