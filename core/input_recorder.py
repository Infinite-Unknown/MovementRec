"""Input recorder using pynput for keyboard/mouse + ctypes WH_MOUSE_LL for X1/X2."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import threading
import time
from typing import Optional

from PySide6.QtCore import QObject, Signal

from pynput import keyboard, mouse

from .models import EventType, InputEvent


# Windows constants for low-level mouse hook
WH_MOUSE_LL = 14
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
WM_MOUSEMOVE = 0x0200

# Raw Input constants
WM_INPUT = 0x00FF
RIDEV_INPUTSINK = 0x00000100
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
HWND_MESSAGE = ctypes.c_void_p(-3)

_user32 = ctypes.WinDLL("user32", use_last_error=True)


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", ctypes.c_ulong),
        ("dwSize", ctypes.c_ulong),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", ctypes.c_ushort),
        ("ulButtons", ctypes.c_ulong),
        ("ulRawButtons", ctypes.c_ulong),
        ("lLastX", ctypes.c_long),
        ("lLastY", ctypes.c_long),
        ("ulExtraInformation", ctypes.c_ulong),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("mouse", RAWMOUSE),
    ]


# Callback type for SetWindowsHookExW
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.c_int,           # return
    ctypes.c_int,           # nCode
    wintypes.WPARAM,        # wParam
    ctypes.POINTER(MSLLHOOKSTRUCT),  # lParam
)


def _key_to_str(key) -> tuple[str, Optional[int]]:
    """Convert a pynput key to (name_string, virtual_key_code)."""
    if isinstance(key, keyboard.Key):
        return key.name, key.value.vk if hasattr(key.value, "vk") else None
    elif isinstance(key, keyboard.KeyCode):
        vk = key.vk if hasattr(key, "vk") else None
        if key.char:
            return key.char, vk
        if vk is not None:
            return f"vk_{vk}", vk
        return str(key), None
    return str(key), None


def _pynput_button_to_str(button) -> str:
    """Convert pynput mouse button to string name."""
    mapping = {
        mouse.Button.left: "left",
        mouse.Button.right: "right",
        mouse.Button.middle: "middle",
    }
    return mapping.get(button, str(button))


class InputRecorder(QObject):
    """Records keyboard, mouse, and scroll events."""

    event_captured = Signal(dict)  # Emits event dict for UI updates

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list[InputEvent] = []
        self._start_time: float = 0.0
        self._final_elapsed: float = 0.0
        self._recording = False
        self._paused = False

        # Filter sets
        self._disabled_keyboard: set[str] = set()
        self._disabled_mouse: set[str] = set()

        # Mouse move throttle
        self.mouse_move_interval_ms: int = 8
        self._last_move_time: float = 0.0

        # Listeners
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None

        # X1/X2 hook thread + Raw Input
        self._xbutton_hook = None
        self._xbutton_thread: Optional[threading.Thread] = None
        self._xbutton_thread_id: Optional[int] = None
        self._hook_callback_ref = None  # prevent GC
        self._raw_input_hwnd = None

        # Raw Input state for locked-cursor detection
        self._prev_raw_cursor_x: int = 0
        self._prev_raw_cursor_y: int = 0
        self._raw_dx_accum: int = 0
        self._raw_dy_accum: int = 0
        self._last_raw_move_time: float = 0.0

    def set_disabled_keys(self, keyboard_keys: set[str], mouse_buttons: set[str]):
        self._disabled_keyboard = keyboard_keys
        self._disabled_mouse = mouse_buttons

    @property
    def events(self) -> list[InputEvent]:
        return self._events

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def elapsed(self) -> float:
        if self._recording:
            return time.perf_counter() - self._start_time
        return self._final_elapsed

    def start(self):
        """Start recording input events."""
        self._events.clear()
        self._start_time = time.perf_counter()
        self._recording = True
        self._paused = False
        self._last_move_time = 0.0
        self._last_raw_move_time = 0.0
        self._raw_dx_accum = 0
        self._raw_dy_accum = 0

        # Initialize cursor position for lock detection
        pt = wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        self._prev_raw_cursor_x = pt.x
        self._prev_raw_cursor_y = pt.y

        # Start pynput listeners
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._keyboard_listener.daemon = True
        self._keyboard_listener.start()

        self._mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
        )
        self._mouse_listener.daemon = True
        self._mouse_listener.start()

        # Start X1/X2 hook thread
        self._start_xbutton_hook()

    def stop(self) -> list[InputEvent]:
        """Stop recording and return captured events."""
        self._final_elapsed = time.perf_counter() - self._start_time
        self._recording = False
        self._paused = False

        if self._keyboard_listener:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None

        self._stop_xbutton_hook()

        return self._events

    def pause(self):
        """Pause recording (events are discarded while paused)."""
        self._paused = True

    def resume(self):
        """Resume recording."""
        self._paused = False

    def _t(self) -> float:
        """Current relative timestamp."""
        return time.perf_counter() - self._start_time

    def _add_event(self, event: InputEvent):
        """Add event to buffer and emit signal."""
        self._events.append(event)
        self.event_captured.emit(event.to_dict())

    # --- Keyboard callbacks ---

    def _on_key_press(self, key):
        if not self._recording or self._paused:
            return
        name, vk = _key_to_str(key)
        if name in self._disabled_keyboard:
            return
        self._add_event(InputEvent(
            type=EventType.KEY, t=self._t(),
            key=name, vk=vk, action="press",
        ))

    def _on_key_release(self, key):
        if not self._recording or self._paused:
            return
        name, vk = _key_to_str(key)
        if name in self._disabled_keyboard:
            return
        self._add_event(InputEvent(
            type=EventType.KEY, t=self._t(),
            key=name, vk=vk, action="release",
        ))

    # --- Mouse callbacks (pynput) ---

    def _on_mouse_move(self, x, y):
        if not self._recording or self._paused:
            return
        now = time.perf_counter()
        if (now - self._last_move_time) * 1000 < self.mouse_move_interval_ms:
            return
        self._last_move_time = now
        self._add_event(InputEvent(
            type=EventType.MOUSE_MOVE, t=self._t(), x=int(x), y=int(y),
        ))

    def _on_mouse_click(self, x, y, button, pressed):
        if not self._recording or self._paused:
            return
        btn_name = _pynput_button_to_str(button)
        if btn_name in self._disabled_mouse:
            return
        self._add_event(InputEvent(
            type=EventType.MOUSE_BUTTON, t=self._t(),
            x=int(x), y=int(y),
            button=btn_name,
            action="press" if pressed else "release",
        ))

    def _on_mouse_scroll(self, x, y, dx, dy):
        if not self._recording or self._paused:
            return
        if "scroll" in self._disabled_mouse:
            return
        self._add_event(InputEvent(
            type=EventType.SCROLL, t=self._t(),
            x=int(x), y=int(y), dx=int(dx), dy=int(dy),
        ))

    # --- X1/X2 button capture via ctypes WH_MOUSE_LL ---

    def _start_xbutton_hook(self):
        """Start a dedicated thread with a low-level mouse hook for X1/X2."""
        self._xbutton_thread = threading.Thread(
            target=self._xbutton_hook_thread, daemon=True
        )
        self._xbutton_thread.start()

    def _xbutton_hook_thread(self):
        """Thread that installs WH_MOUSE_LL, registers Raw Input, and runs a message pump."""
        self._xbutton_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        def low_level_mouse_proc(nCode, wParam, lParam):
            if nCode >= 0 and self._recording and not self._paused:
                if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                    info = lParam.contents
                    hi_word = (info.mouseData >> 16) & 0xFFFF
                    if hi_word == XBUTTON1:
                        btn = "x1"
                    elif hi_word == XBUTTON2:
                        btn = "x2"
                    else:
                        btn = f"x_unknown_{hi_word}"

                    if btn not in self._disabled_mouse:
                        action = "press" if wParam == WM_XBUTTONDOWN else "release"
                        event = InputEvent(
                            type=EventType.MOUSE_BUTTON,
                            t=self._t(),
                            x=info.pt.x,
                            y=info.pt.y,
                            button=btn,
                            action=action,
                        )
                        self._add_event(event)

            return _user32.CallNextHookEx(None, nCode, wParam, lParam)

        # Must keep a reference to prevent garbage collection
        self._hook_callback_ref = HOOKPROC(low_level_mouse_proc)

        self._xbutton_hook = _user32.SetWindowsHookExW(
            WH_MOUSE_LL,
            self._hook_callback_ref,
            None,
            0,
        )

        if not self._xbutton_hook:
            return

        # Create message-only window for Raw Input
        self._raw_input_hwnd = _user32.CreateWindowExW(
            0, "Static", "", 0, 0, 0, 0, 0,
            HWND_MESSAGE, None, None, None,
        )

        if self._raw_input_hwnd:
            # Register for raw mouse input
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = 0x01  # Generic Desktop
            rid.usUsage = 0x02      # Mouse
            rid.dwFlags = RIDEV_INPUTSINK
            rid.hwndTarget = self._raw_input_hwnd
            _user32.RegisterRawInputDevices(
                ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE),
            )

        # Message pump to keep the hook alive and receive WM_INPUT
        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_INPUT:
                self._process_raw_input(msg.lParam)
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

        # Cleanup
        if self._raw_input_hwnd:
            _user32.DestroyWindow(self._raw_input_hwnd)
            self._raw_input_hwnd = None
        _user32.UnhookWindowsHookEx(self._xbutton_hook)
        self._xbutton_hook = None

    def _process_raw_input(self, hRawInput):
        """Extract raw mouse deltas from WM_INPUT and record if cursor is locked."""
        if not self._recording or self._paused:
            return

        # Get required buffer size
        size = ctypes.c_uint()
        _user32.GetRawInputData(
            hRawInput, RID_INPUT, None,
            ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER),
        )
        if size.value == 0:
            return

        # Read raw input data
        buf = (ctypes.c_byte * size.value)()
        _user32.GetRawInputData(
            hRawInput, RID_INPUT, buf,
            ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER),
        )

        raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents

        if raw.header.dwType != RIM_TYPEMOUSE:
            return

        # Only handle relative mouse movement (usFlags == 0)
        if raw.mouse.usFlags != 0:
            return

        dx = raw.mouse.lLastX
        dy = raw.mouse.lLastY
        if dx == 0 and dy == 0:
            return

        # Check if cursor appears locked (position barely changed)
        pt = wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))

        cursor_dist = (abs(pt.x - self._prev_raw_cursor_x)
                       + abs(pt.y - self._prev_raw_cursor_y))
        self._prev_raw_cursor_x = pt.x
        self._prev_raw_cursor_y = pt.y

        if cursor_dist > 2:
            # Cursor is moving freely — pynput handles this
            self._raw_dx_accum = 0
            self._raw_dy_accum = 0
            return

        # Cursor is locked — accumulate deltas and throttle
        self._raw_dx_accum += dx
        self._raw_dy_accum += dy

        now = time.perf_counter()
        if (now - self._last_raw_move_time) * 1000 < self.mouse_move_interval_ms:
            return

        total_dx = self._raw_dx_accum
        total_dy = self._raw_dy_accum
        self._raw_dx_accum = 0
        self._raw_dy_accum = 0
        self._last_raw_move_time = now

        if total_dx != 0 or total_dy != 0:
            self._add_event(InputEvent(
                type=EventType.MOUSE_MOVE_RELATIVE,
                t=self._t(),
                dx=total_dx,
                dy=total_dy,
            ))

    def _stop_xbutton_hook(self):
        """Stop the X1/X2 hook thread by posting WM_QUIT."""
        if self._xbutton_thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(
                self._xbutton_thread_id, 0x0012, 0, 0  # WM_QUIT
            )
            self._xbutton_thread_id = None
        if self._xbutton_thread is not None:
            self._xbutton_thread.join(timeout=2.0)
            self._xbutton_thread = None
        self._hook_callback_ref = None
