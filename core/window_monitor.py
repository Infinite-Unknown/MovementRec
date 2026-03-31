"""Window enumeration and focus tracking using pywin32."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

import win32gui
import win32process


# For getting process name without psutil
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _get_exe_name(hwnd: int) -> str:
    """Get the executable name for a window handle."""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(260)
            if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                # Return just the filename
                path = buf.value
                return path.rsplit("\\", 1)[-1] if "\\" in path else path
            return ""
        finally:
            _kernel32.CloseHandle(handle)
    except Exception:
        return ""


class WindowInfo:
    __slots__ = ("hwnd", "title", "exe")

    def __init__(self, hwnd: int, title: str, exe: str):
        self.hwnd = hwnd
        self.title = title
        self.exe = exe

    def display_text(self) -> str:
        if self.exe:
            return f"{self.title} ({self.exe})"
        return self.title


class WindowMonitor(QObject):
    """Monitors window focus and enumerates visible windows."""

    focus_gained = Signal()
    focus_lost = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_hwnd: Optional[int] = None
        self._target_exe: str = ""
        self._was_focused = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(100)  # 100ms polling
        self._poll_timer.timeout.connect(self._check_focus)

    def list_windows(self) -> list[WindowInfo]:
        """Return list of visible windows with non-empty titles."""
        windows: list[WindowInfo] = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title or title == "Program Manager":
                return True
            exe = _get_exe_name(hwnd)
            windows.append(WindowInfo(hwnd, title, exe))
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass
        return windows

    def set_target(self, hwnd: int, exe: str = ""):
        """Set the target window to monitor."""
        self._target_hwnd = hwnd
        self._target_exe = exe
        self._was_focused = False

    def start_monitoring(self):
        """Start polling for focus changes."""
        if self._target_hwnd is not None:
            self._was_focused = self._is_target_focused()
            self._poll_timer.start()

    def stop_monitoring(self):
        """Stop polling."""
        self._poll_timer.stop()
        self._was_focused = False

    def is_target_focused(self) -> bool:
        return self._is_target_focused()

    def _is_target_focused(self) -> bool:
        """Check if the target window (or any window of same exe) is focused."""
        try:
            fg = win32gui.GetForegroundWindow()
            if fg == self._target_hwnd:
                return True
            # Also match by exe name in case the window handle changed (e.g. dialog)
            if self._target_exe:
                fg_exe = _get_exe_name(fg)
                if fg_exe and fg_exe.lower() == self._target_exe.lower():
                    return True
            return False
        except Exception:
            return False

    def _check_focus(self):
        """Timer callback: emit signals on focus transitions."""
        focused = self._is_target_focused()
        if focused and not self._was_focused:
            self._was_focused = True
            self.focus_gained.emit()
        elif not focused and self._was_focused:
            self._was_focused = False
            self.focus_lost.emit()

    @property
    def target_hwnd(self) -> Optional[int]:
        return self._target_hwnd
