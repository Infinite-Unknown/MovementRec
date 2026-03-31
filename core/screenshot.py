"""Window screenshot capture using mss + Pillow."""

from __future__ import annotations

import io
from typing import Optional

import win32gui
import mss
from PIL import Image


def capture_window_thumbnail(
    hwnd: int,
    max_size: tuple[int, int] = (320, 180),
) -> Optional[bytes]:
    """Capture a screenshot of the given window and return PNG bytes of thumbnail.

    Returns None if the window is not visible or capture fails.
    """
    try:
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None

        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Resize to thumbnail preserving aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def capture_full_window(hwnd: int) -> Optional[bytes]:
    """Capture a full-size screenshot of the given window. Returns PNG bytes."""
    try:
        rect = win32gui.GetWindowRect(hwnd)
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None

        with mss.mss() as sct:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None
