"""Hotkey configuration dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class KeyCaptureEdit(QLineEdit):
    """A QLineEdit that captures a single key press for hotkey assignment."""

    key_captured = Signal(str)

    def __init__(self, current_key: str = "", parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setText(current_key)
        self.setPlaceholderText("Click and press a key...")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLineEdit {
                border: 2px solid #0078D4;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
                font-weight: bold;
                background: #3C3C3C;
                color: #E0E0E0;
            }
            QLineEdit:focus {
                border-color: #1A8AE0;
                background: #2A3A4A;
            }
        """)
        self._captured_key = current_key

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        # Map Qt key to a human-readable name
        key_name = self._qt_key_to_name(key)
        if key_name:
            self._captured_key = key_name
            self.setText(key_name)
            self.key_captured.emit(key_name)

    def captured_key(self) -> str:
        return self._captured_key

    @staticmethod
    def _qt_key_to_name(key: int) -> str:
        """Convert Qt key code to a pynput-compatible key name."""
        qt_to_name = {
            Qt.Key.Key_F1: "F1", Qt.Key.Key_F2: "F2", Qt.Key.Key_F3: "F3",
            Qt.Key.Key_F4: "F4", Qt.Key.Key_F5: "F5", Qt.Key.Key_F6: "F6",
            Qt.Key.Key_F7: "F7", Qt.Key.Key_F8: "F8", Qt.Key.Key_F9: "F9",
            Qt.Key.Key_F10: "F10", Qt.Key.Key_F11: "F11", Qt.Key.Key_F12: "F12",
            Qt.Key.Key_Escape: "Escape",
            Qt.Key.Key_Tab: "Tab",
            Qt.Key.Key_Backspace: "Backspace",
            Qt.Key.Key_Return: "Return",
            Qt.Key.Key_Enter: "Enter",
            Qt.Key.Key_Insert: "Insert",
            Qt.Key.Key_Delete: "Delete",
            Qt.Key.Key_Pause: "Pause",
            Qt.Key.Key_Print: "Print",
            Qt.Key.Key_Home: "Home",
            Qt.Key.Key_End: "End",
            Qt.Key.Key_Left: "Left",
            Qt.Key.Key_Up: "Up",
            Qt.Key.Key_Right: "Right",
            Qt.Key.Key_Down: "Down",
            Qt.Key.Key_PageUp: "PageUp",
            Qt.Key.Key_PageDown: "PageDown",
            Qt.Key.Key_Space: "Space",
            Qt.Key.Key_ScrollLock: "ScrollLock",
            Qt.Key.Key_NumLock: "NumLock",
            Qt.Key.Key_CapsLock: "CapsLock",
        }
        if key in qt_to_name:
            return qt_to_name[key]
        # For letter/number keys
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key)
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        return ""


# Map human key names to pynput Key attributes
KEYBIND_TO_PYNPUT = {
    "F1": "f1", "F2": "f2", "F3": "f3", "F4": "f4",
    "F5": "f5", "F6": "f6", "F7": "f7", "F8": "f8",
    "F9": "f9", "F10": "f10", "F11": "f11", "F12": "f12",
    "Escape": "esc", "Tab": "tab", "Backspace": "backspace",
    "Return": "enter", "Enter": "enter",
    "Insert": "insert", "Delete": "delete",
    "Pause": "pause", "Print": "print_screen",
    "Home": "home", "End": "end",
    "Left": "left", "Up": "up", "Right": "right", "Down": "down",
    "PageUp": "page_up", "PageDown": "page_down",
    "Space": "space", "ScrollLock": "scroll_lock",
    "NumLock": "num_lock", "CapsLock": "caps_lock",
}


def keybind_to_pynput_str(key_name: str) -> str:
    """Convert a human-readable key name to a pynput hotkey string."""
    pynput_name = KEYBIND_TO_PYNPUT.get(key_name)
    if pynput_name:
        return f"<{pynput_name}>"
    # Single character keys
    if len(key_name) == 1:
        return key_name.lower()
    return f"<{key_name.lower()}>"


class KeybindDialog(QDialog):
    """Dialog for configuring global hotkeys."""

    def __init__(self, current_keybinds: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keybind Settings")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        info = QLabel("Click a field and press a key to set the hotkey.")
        info.setStyleSheet("color: #AAAAAA; margin-bottom: 8px;")
        layout.addWidget(info)

        form = QFormLayout()

        self._start_stop = KeyCaptureEdit(current_keybinds.get("start_stop", "F9"))
        form.addRow("Start / Stop Recording:", self._start_stop)

        self._pause_resume = KeyCaptureEdit(current_keybinds.get("pause_resume", "F10"))
        form.addRow("Pause / Resume:", self._pause_resume)

        layout.addLayout(form)

        # Restore defaults
        defaults_btn = QPushButton("Restore Defaults")
        defaults_btn.clicked.connect(self._restore_defaults)
        layout.addWidget(defaults_btn)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _restore_defaults(self):
        self._start_stop.setText("F9")
        self._start_stop._captured_key = "F9"
        self._pause_resume.setText("F10")
        self._pause_resume._captured_key = "F10"

    def get_keybinds(self) -> dict:
        return {
            "start_stop": self._start_stop.captured_key() or "F9",
            "pause_resume": self._pause_resume.captured_key() or "F10",
        }
