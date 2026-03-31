"""Playback engine — replays recorded events, supports multiple concurrent sessions."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import json
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from pynput.keyboard import Controller as KbController, Key as PynputKey, KeyCode

from .models import EventType, InputEvent, PlaybackSlot, Recording


# --- Windows SendInput for all mouse buttons ---

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

SM_CXSCREEN = 0
SM_CYSCREEN = 1

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION),
    ]

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
_user32.SendInput.restype = ctypes.c_uint
_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int


def _to_absolute(x: int, y: int) -> tuple[int, int]:
    """Convert pixel (x, y) to SendInput absolute coordinates (0-65535)."""
    screen_w = _user32.GetSystemMetrics(SM_CXSCREEN)
    screen_h = _user32.GetSystemMetrics(SM_CYSCREEN)
    abs_x = int(x * 65536 / screen_w)
    abs_y = int(y * 65536 / screen_h)
    return abs_x, abs_y

# Map button name + action to (dwFlags, mouseData)
_BUTTON_FLAGS = {
    ("left", "press"):    (MOUSEEVENTF_LEFTDOWN, 0),
    ("left", "release"):  (MOUSEEVENTF_LEFTUP, 0),
    ("right", "press"):   (MOUSEEVENTF_RIGHTDOWN, 0),
    ("right", "release"): (MOUSEEVENTF_RIGHTUP, 0),
    ("middle", "press"):  (MOUSEEVENTF_MIDDLEDOWN, 0),
    ("middle", "release"):(MOUSEEVENTF_MIDDLEUP, 0),
    ("x1", "press"):      (MOUSEEVENTF_XDOWN, XBUTTON1),
    ("x1", "release"):    (MOUSEEVENTF_XUP, XBUTTON1),
    ("x2", "press"):      (MOUSEEVENTF_XDOWN, XBUTTON2),
    ("x2", "release"):    (MOUSEEVENTF_XUP, XBUTTON2),
}


MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000
WHEEL_DELTA = 120


def _send_relative_move(dx: int, dy: int):
    """Send relative mouse movement via SendInput (no MOUSEEVENTF_ABSOLUTE)."""
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, None)
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _set_cursor_pos(x: int, y: int):
    """Move cursor via SendInput with MOUSEEVENTF_ABSOLUTE."""
    abs_x, abs_y = _to_absolute(x, y)
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = MOUSEINPUT(
        abs_x, abs_y, 0,
        MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
        0, None,
    )
    _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _send_mouse_button(button: str, action: str,
                       x: Optional[int] = None, y: Optional[int] = None):
    """Send mouse button press/release via SendInput, optionally with position."""
    key = (button, action)
    if key not in _BUTTON_FLAGS:
        return
    flags, data = _BUTTON_FLAGS[key]

    if x is not None and y is not None:
        abs_x, abs_y = _to_absolute(x, y)
        inputs = (INPUT * 2)()
        # Move to absolute position
        inputs[0].type = INPUT_MOUSE
        inputs[0].mi = MOUSEINPUT(
            abs_x, abs_y, 0,
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
            0, None,
        )
        # Button action with position data
        inputs[1].type = INPUT_MOUSE
        inputs[1].mi = MOUSEINPUT(
            abs_x, abs_y, data,
            flags | MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
            0, None,
        )
        _user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    else:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi = MOUSEINPUT(0, 0, data, flags, 0, None)
        _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def _send_scroll(x: int, y: int, dx: int, dy: int):
    """Send scroll via SendInput with absolute positioning."""
    abs_x, abs_y = _to_absolute(x, y)
    if dy != 0:
        inputs = (INPUT * 2)()
        inputs[0].type = INPUT_MOUSE
        inputs[0].mi = MOUSEINPUT(
            abs_x, abs_y, 0,
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
            0, None,
        )
        inputs[1].type = INPUT_MOUSE
        inputs[1].mi = MOUSEINPUT(
            0, 0, ctypes.c_ulong(dy * WHEEL_DELTA).value,
            MOUSEEVENTF_WHEEL, 0, None,
        )
        _user32.SendInput(2, inputs, ctypes.sizeof(INPUT))
    if dx != 0:
        inputs = (INPUT * 2)()
        inputs[0].type = INPUT_MOUSE
        inputs[0].mi = MOUSEINPUT(
            abs_x, abs_y, 0,
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
            0, None,
        )
        inputs[1].type = INPUT_MOUSE
        inputs[1].mi = MOUSEINPUT(
            0, 0, ctypes.c_ulong(dx * WHEEL_DELTA).value,
            MOUSEEVENTF_HWHEEL, 0, None,
        )
        _user32.SendInput(2, inputs, ctypes.sizeof(INPUT))


_MOUSE_EVENT_TYPES = {
    EventType.MOUSE_MOVE,
    EventType.MOUSE_MOVE_RELATIVE,
    EventType.MOUSE_BUTTON,
    EventType.SCROLL,
}
_KEY_EVENT_TYPES = {EventType.KEY}


# Mapping from recording key strings back to pynput objects
_SPECIAL_KEYS = {k.name: k for k in PynputKey}

def _str_to_pynput_key(key_str: str):
    """Convert a key string (from recording) to a pynput key object."""
    if key_str in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[key_str]
    if len(key_str) == 1:
        return KeyCode.from_char(key_str)
    if key_str.startswith("vk_"):
        try:
            return KeyCode.from_vk(int(key_str[3:]))
        except ValueError:
            pass
    return None



class PlaybackEngine(QObject):
    """Replays a single recording on a background thread."""

    playback_started = Signal()
    playback_stopped = Signal()
    progress_updated = Signal(float)  # 0.0 – 1.0
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._playing = False
        self._speed = 1.0
        self._loop = False
        self._event_filter = "all"  # "all" | "mouse" | "keyboard"

    @property
    def is_playing(self) -> bool:
        return self._playing

    def play(self, recording: Recording, speed: float = 1.0,
             loop: bool = False, event_filter: str = "all"):
        if self._playing:
            return
        self._speed = max(0.1, min(speed, 10.0))
        self._loop = loop
        self._event_filter = event_filter
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._playback_loop, args=(recording,), daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _should_skip(self, ev: InputEvent) -> bool:
        if self._event_filter == "mouse" and ev.type in _KEY_EVENT_TYPES:
            return True
        if self._event_filter == "keyboard" and ev.type in _MOUSE_EVENT_TYPES:
            return True
        return False

    def _playback_loop(self, recording: Recording):
        self._playing = True
        self.playback_started.emit()

        kb = KbController()
        events = recording.events

        if not events:
            self._playing = False
            self.playback_stopped.emit()
            return

        try:
            while True:
                total_t = events[-1].t if events else 0
                prev_t = 0.0

                for i, ev in enumerate(events):
                    if self._stop_event.is_set():
                        self._playing = False
                        self.playback_stopped.emit()
                        return

                    delay = (ev.t - prev_t) / self._speed
                    if delay > 0:
                        end = time.perf_counter() + delay
                        while time.perf_counter() < end:
                            if self._stop_event.is_set():
                                self._playing = False
                                self.playback_stopped.emit()
                                return
                            time.sleep(min(0.01, end - time.perf_counter()))
                    prev_t = ev.t

                    if not self._should_skip(ev):
                        self._execute_event(ev, kb)

                    if total_t > 0:
                        self.progress_updated.emit(ev.t / total_t)

                if not self._loop:
                    break

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self._playing = False
            self.playback_stopped.emit()

    def _execute_event(self, ev: InputEvent, kb: KbController):
        if ev.type == EventType.MOUSE_MOVE:
            _set_cursor_pos(ev.x, ev.y)

        elif ev.type == EventType.MOUSE_MOVE_RELATIVE:
            _send_relative_move(ev.dx or 0, ev.dy or 0)

        elif ev.type == EventType.MOUSE_BUTTON:
            _send_mouse_button(ev.button, ev.action, ev.x, ev.y)

        elif ev.type == EventType.KEY:
            key_obj = _str_to_pynput_key(ev.key)
            if key_obj is None and ev.vk is not None:
                key_obj = KeyCode.from_vk(ev.vk)
            if key_obj is not None:
                if ev.action == "press":
                    kb.press(key_obj)
                else:
                    kb.release(key_obj)

        elif ev.type == EventType.SCROLL:
            _send_scroll(ev.x, ev.y, ev.dx or 0, ev.dy or 0)


class PlaybackManager(QObject):
    """Manages multiple concurrent playback sessions."""

    session_started = Signal(str, str, float)   # slot_id, recording_name, duration
    session_stopped = Signal(str)               # slot_id
    session_progress = Signal(str, float)       # slot_id, 0.0-1.0
    all_stopped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sessions: dict[str, PlaybackEngine] = {}
        self._rec_names: dict[str, str] = {}    # slot_id -> recording name
        self._rec_durations: dict[str, float] = {}  # slot_id -> duration

    def start(self, slot_id: str, recording: Recording, slot: PlaybackSlot):
        if slot_id in self._sessions:
            return
        engine = PlaybackEngine(self)
        self._sessions[slot_id] = engine
        self._rec_names[slot_id] = recording.name
        self._rec_durations[slot_id] = recording.duration_seconds

        # Route engine signals through manager with slot_id
        engine.playback_started.connect(
            lambda sid=slot_id: self.session_started.emit(
                sid, self._rec_names.get(sid, ""), self._rec_durations.get(sid, 0)))
        engine.playback_stopped.connect(lambda sid=slot_id: self._on_session_stopped(sid))
        engine.progress_updated.connect(
            lambda pct, sid=slot_id: self.session_progress.emit(sid, pct))

        engine.play(recording, speed=slot.speed, loop=slot.loop,
                    event_filter=slot.event_filter)

    def stop(self, slot_id: str):
        engine = self._sessions.get(slot_id)
        if engine:
            engine.stop()

    def toggle(self, slot_id: str, recording: Recording, slot: PlaybackSlot):
        if slot_id in self._sessions:
            self.stop(slot_id)
        else:
            self.start(slot_id, recording, slot)

    def stop_all(self):
        for sid in list(self._sessions):
            self.stop(sid)

    def is_playing(self, slot_id: str) -> bool:
        return slot_id in self._sessions

    def active_sessions(self) -> list[str]:
        return list(self._sessions)

    def _on_session_stopped(self, slot_id: str):
        self._sessions.pop(slot_id, None)
        self._rec_names.pop(slot_id, None)
        self._rec_durations.pop(slot_id, None)
        self.session_stopped.emit(slot_id)
        if not self._sessions:
            self.all_stopped.emit()


def load_recording(path: Path) -> Recording:
    """Load a full recording (with events) from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return Recording.from_dict(d)
