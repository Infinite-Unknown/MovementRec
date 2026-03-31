"""Visual keyboard layout widget with toggleable keys for recording filter."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

# Key layout: each row is a list of (key_id, display_label, col_span)
KEYBOARD_LAYOUT = [
    # Row 0: Escape + F-keys
    [
        ("esc", "Esc", 2),
        (None, "", 1),
        ("f1", "F1", 2), ("f2", "F2", 2), ("f3", "F3", 2), ("f4", "F4", 2),
        (None, "", 1),
        ("f5", "F5", 2), ("f6", "F6", 2), ("f7", "F7", 2), ("f8", "F8", 2),
        (None, "", 1),
        ("f9", "F9", 2), ("f10", "F10", 2), ("f11", "F11", 2), ("f12", "F12", 2),
    ],
    # Row 1: Number row
    [
        ("`", "`", 2), ("1", "1", 2), ("2", "2", 2), ("3", "3", 2),
        ("4", "4", 2), ("5", "5", 2), ("6", "6", 2), ("7", "7", 2),
        ("8", "8", 2), ("9", "9", 2), ("0", "0", 2), ("-", "-", 2),
        ("=", "=", 2), ("backspace", "Bksp", 4),
    ],
    # Row 2: QWERTY
    [
        ("tab", "Tab", 3),
        ("q", "Q", 2), ("w", "W", 2), ("e", "E", 2), ("r", "R", 2),
        ("t", "T", 2), ("y", "Y", 2), ("u", "U", 2), ("i", "I", 2),
        ("o", "O", 2), ("p", "P", 2), ("[", "[", 2), ("]", "]", 2),
        ("\\", "\\", 3),
    ],
    # Row 3: Home row
    [
        ("caps_lock", "Caps", 4),
        ("a", "A", 2), ("s", "S", 2), ("d", "D", 2), ("f", "F", 2),
        ("g", "G", 2), ("h", "H", 2), ("j", "J", 2), ("k", "K", 2),
        ("l", "L", 2), (";", ";", 2), ("'", "'", 2),
        ("enter", "Enter", 4),
    ],
    # Row 4: Shift row
    [
        ("shift", "LShift", 5),
        ("z", "Z", 2), ("x", "X", 2), ("c", "C", 2), ("v", "V", 2),
        ("b", "B", 2), ("n", "N", 2), ("m", "M", 2), (",", ",", 2),
        (".", ".", 2), ("/", "/", 2),
        ("shift_r", "RShift", 5),
    ],
    # Row 5: Bottom row
    [
        ("ctrl_l", "Ctrl", 3), ("cmd", "Win", 2), ("alt_l", "Alt", 3),
        ("space", "Space", 12),
        ("alt_r", "RAlt", 3), ("cmd_r", "RWin", 2), ("menu", "Menu", 2),
        ("ctrl_r", "RCtrl", 3),
    ],
]

NAV_LAYOUT = [
    [("print_screen", "PrtSc", 2), ("scroll_lock", "ScrLk", 2), ("pause", "Pause", 2)],
    [("insert", "Ins", 2), ("home", "Home", 2), ("page_up", "PgUp", 2)],
    [("delete", "Del", 2), ("end", "End", 2), ("page_down", "PgDn", 2)],
    [],
    [(None, "", 2), ("up", "Up", 2), (None, "", 2)],
    [("left", "Left", 2), ("down", "Down", 2), ("right", "Right", 2)],
]

NUMPAD_LAYOUT = [
    [("num_lock", "Num", 2), ("num_/", "/", 2), ("num_*", "*", 2), ("num_-", "-", 2)],
    [("num_7", "7", 2), ("num_8", "8", 2), ("num_9", "9", 2), ("num_+", "+", 2)],
    [("num_4", "4", 2), ("num_5", "5", 2), ("num_6", "6", 2), (None, "", 2)],
    [("num_1", "1", 2), ("num_2", "2", 2), ("num_3", "3", 2), ("num_enter", "Ent", 2)],
    [("num_0", "0", 4), ("num_.", ".", 2), (None, "", 2)],
]

ENABLED_STYLE = """
    QPushButton {
        background-color: #2E4A2E;
        border: 1px solid #4CAF50;
        border-radius: 4px;
        font-size: 10px;
        font-weight: bold;
        padding: 2px;
        min-height: 30px;
        color: #B0E0B0;
    }
    QPushButton:hover { background-color: #3A5C3A; border-color: #66BB6A; }
"""

DISABLED_STYLE = """
    QPushButton {
        background-color: #3C3C3C;
        border: 1px solid #555;
        border-radius: 4px;
        font-size: 10px;
        font-weight: bold;
        padding: 2px;
        min-height: 30px;
        color: #777;
    }
    QPushButton:hover { background-color: #4A4A4A; border-color: #888; }
"""

TOOLBAR_BTN = """
    QPushButton {
        background-color: #3C3C3C;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 6px 16px;
        font-size: 11px;
        font-weight: bold;
        color: #E0E0E0;
    }
    QPushButton:hover { background-color: #4A4A4A; }
"""

ENABLE_ALL_BTN = """
    QPushButton {
        background-color: #2E4A2E;
        border: 1px solid #4CAF50;
        border-radius: 4px;
        padding: 6px 16px;
        font-size: 11px;
        font-weight: bold;
        color: #B0E0B0;
    }
    QPushButton:hover { background-color: #3A5C3A; }
"""

DISABLE_ALL_BTN = """
    QPushButton {
        background-color: #4A2020;
        border: 1px solid #EF5350;
        border-radius: 4px;
        padding: 6px 16px;
        font-size: 11px;
        font-weight: bold;
        color: #FF8A80;
    }
    QPushButton:hover { background-color: #5C2828; }
"""


class KeyboardWidget(QWidget):
    """Interactive visual keyboard. Click keys to enable/disable for recording."""

    disabled_keys_changed = Signal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._disabled: set[str] = set()
        self._buttons: dict[str, QPushButton] = {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Top bar: label + enable/disable all buttons
        top_bar = QHBoxLayout()
        label = QLabel("Click keys to toggle recording  |  Green = recorded  |  Grey = ignored")
        label.setStyleSheet("font-size: 12px; color: #AAAAAA;")
        top_bar.addWidget(label)
        top_bar.addStretch()

        self._enable_all_btn = QPushButton("Enable All")
        self._enable_all_btn.setStyleSheet(ENABLE_ALL_BTN)
        self._enable_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._enable_all_btn.clicked.connect(self.enable_all)
        top_bar.addWidget(self._enable_all_btn)

        self._disable_all_btn = QPushButton("Disable All")
        self._disable_all_btn.setStyleSheet(DISABLE_ALL_BTN)
        self._disable_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._disable_all_btn.clicked.connect(self.disable_all)
        top_bar.addWidget(self._disable_all_btn)

        main_layout.addLayout(top_bar)

        # Keyboard grid: main keyboard | nav cluster | numpad
        h_layout = QGridLayout()
        h_layout.setSpacing(4)
        main_layout.addLayout(h_layout, 1)

        main_kb = QWidget()
        main_grid = QGridLayout(main_kb)
        main_grid.setSpacing(3)
        main_grid.setContentsMargins(0, 0, 0, 0)
        self._populate_grid(main_grid, KEYBOARD_LAYOUT)
        h_layout.addWidget(main_kb, 0, 0)

        nav_kb = QWidget()
        nav_grid = QGridLayout(nav_kb)
        nav_grid.setSpacing(3)
        nav_grid.setContentsMargins(12, 0, 12, 0)
        self._populate_grid(nav_grid, NAV_LAYOUT)
        h_layout.addWidget(nav_kb, 0, 1)

        num_kb = QWidget()
        num_grid = QGridLayout(num_kb)
        num_grid.setSpacing(3)
        num_grid.setContentsMargins(0, 0, 0, 0)
        self._populate_grid(num_grid, NUMPAD_LAYOUT)
        h_layout.addWidget(num_kb, 0, 2)

        h_layout.setColumnStretch(0, 3)
        h_layout.setColumnStretch(1, 1)
        h_layout.setColumnStretch(2, 1)

        # Default: all keys disabled (user opts in)
        self._init_all_disabled()

    def _init_all_disabled(self):
        """Set all keys to disabled by default."""
        self._disabled = set(self._buttons.keys())
        for btn in self._buttons.values():
            btn.setStyleSheet(DISABLED_STYLE)

    def _populate_grid(self, grid: QGridLayout, layout_data: list):
        for row_idx, row in enumerate(layout_data):
            col = 0
            for item in row:
                key_id, label, span = item
                if key_id is None:
                    col += span
                    continue
                btn = QPushButton(label)
                btn.setStyleSheet(DISABLED_STYLE)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setProperty("key_id", key_id)
                btn.clicked.connect(lambda checked, kid=key_id: self._toggle_key(kid))
                grid.addWidget(btn, row_idx, col, 1, span)
                self._buttons[key_id] = btn
                col += span

    def _toggle_key(self, key_id: str):
        if key_id in self._disabled:
            self._disabled.discard(key_id)
            self._buttons[key_id].setStyleSheet(ENABLED_STYLE)
        else:
            self._disabled.add(key_id)
            self._buttons[key_id].setStyleSheet(DISABLED_STYLE)
        self.disabled_keys_changed.emit(self._disabled.copy())

    def get_disabled_keys(self) -> set[str]:
        return self._disabled.copy()

    def set_disabled_keys(self, keys: set[str]):
        for kid, btn in self._buttons.items():
            if kid in keys:
                btn.setStyleSheet(DISABLED_STYLE)
            else:
                btn.setStyleSheet(ENABLED_STYLE)
        self._disabled = set(keys)

    def enable_all(self):
        self.set_disabled_keys(set())
        self.disabled_keys_changed.emit(self._disabled.copy())

    def disable_all(self):
        self.set_disabled_keys(set(self._buttons.keys()))
        self.disabled_keys_changed.emit(self._disabled.copy())
