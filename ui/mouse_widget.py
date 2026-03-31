"""Visual mouse widget with toggleable buttons for recording filter."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


MOUSE_BUTTONS = ["left", "right", "middle", "x1", "x2", "scroll"]

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


class MouseDiagram(QWidget):
    """Custom painted mouse diagram with clickable zones."""

    button_toggled = Signal(str, bool)  # button_id, is_enabled

    def __init__(self, parent=None):
        super().__init__(parent)
        self._disabled: set[str] = set(MOUSE_BUTTONS)  # all disabled by default
        self.setMinimumSize(240, 360)
        self.setMaximumSize(320, 440)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._zones: list[tuple[str, str, tuple[float, float, float, float]]] = [
            ("left",   "Left",      (0.08, 0.05, 0.38, 0.25)),
            ("right",  "Right",     (0.54, 0.05, 0.38, 0.25)),
            ("middle", "Middle",    (0.38, 0.05, 0.24, 0.20)),
            ("x1",     "X1\nBack",  (0.02, 0.40, 0.18, 0.15)),
            ("x2",     "X2\nFwd",   (0.02, 0.28, 0.18, 0.12)),
            ("scroll", "Scroll",    (0.38, 0.20, 0.24, 0.10)),
        ]

    def _get_zone_rect(self, zone_fracs: tuple[float, float, float, float]) -> QRectF:
        w, h = self.width(), self.height()
        return QRectF(zone_fracs[0] * w, zone_fracs[1] * h,
                       zone_fracs[2] * w, zone_fracs[3] * h)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Mouse body
        body = QPainterPath()
        body.addRoundedRect(QRectF(w * 0.1, h * 0.03, w * 0.8, h * 0.92), 40, 30)
        p.setPen(QPen(QColor("#555"), 2))
        p.setBrush(QBrush(QColor("#2D2D2D")))
        p.drawPath(body)

        # Side button area
        side_bg = QPainterPath()
        side_bg.addRoundedRect(QRectF(w * 0.01, h * 0.26, w * 0.20, h * 0.32), 8, 8)
        p.setBrush(QBrush(QColor("#383838")))
        p.drawPath(side_bg)

        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(font)

        for btn_id, label, fracs in self._zones:
            rect = self._get_zone_rect(fracs)
            enabled = btn_id not in self._disabled

            if enabled:
                bg = QColor("#2E4A2E")
                border = QColor("#4CAF50")
                text_color = QColor("#B0E0B0")
            else:
                bg = QColor("#3C3C3C")
                border = QColor("#555")
                text_color = QColor("#777")

            path = QPainterPath()
            path.addRoundedRect(rect, 6, 6)
            p.setPen(QPen(border, 1.5))
            p.setBrush(QBrush(bg))
            p.drawPath(path)

            p.setPen(text_color)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        # Divider
        p.setPen(QPen(QColor("#555"), 1))
        p.drawLine(int(w * 0.50), int(h * 0.05), int(w * 0.50), int(h * 0.28))

        p.end()

    def mousePressEvent(self, event):
        pos = event.position()
        for btn_id, label, fracs in self._zones:
            rect = self._get_zone_rect(fracs)
            if rect.contains(pos):
                if btn_id in self._disabled:
                    self._disabled.discard(btn_id)
                    self.button_toggled.emit(btn_id, True)
                else:
                    self._disabled.add(btn_id)
                    self.button_toggled.emit(btn_id, False)
                self.update()
                return
        super().mousePressEvent(event)

    def get_disabled_buttons(self) -> set[str]:
        return self._disabled.copy()

    def set_disabled_buttons(self, buttons: set[str]):
        self._disabled = set(buttons)
        self.update()


class MouseWidget(QWidget):
    """Container for mouse diagram with label, controls, and enable/disable all."""

    disabled_buttons_changed = Signal(set)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top bar
        top_bar = QHBoxLayout()
        label = QLabel("Click mouse buttons to toggle  |  Green = recorded  |  Grey = ignored")
        label.setStyleSheet("font-size: 12px; color: #AAAAAA;")
        top_bar.addWidget(label)
        top_bar.addStretch()

        enable_btn = QPushButton("Enable All")
        enable_btn.setStyleSheet(ENABLE_ALL_BTN)
        enable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        enable_btn.clicked.connect(self._enable_all)
        top_bar.addWidget(enable_btn)

        disable_btn = QPushButton("Disable All")
        disable_btn.setStyleSheet(DISABLE_ALL_BTN)
        disable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        disable_btn.clicked.connect(self._disable_all)
        top_bar.addWidget(disable_btn)

        layout.addLayout(top_bar)

        # Mouse diagram
        self._diagram = MouseDiagram()
        self._diagram.button_toggled.connect(self._on_button_toggled)
        layout.addWidget(self._diagram, 1, Qt.AlignmentFlag.AlignCenter)

        # Legend
        legend = QLabel(
            "Left / Right / Middle: Standard buttons\n"
            "X1 (Back) / X2 (Forward): Side buttons (Mouse 4 & 5)\n"
            "Scroll: Mouse wheel events"
        )
        legend.setStyleSheet("font-size: 11px; color: #888; margin-top: 8px;")
        layout.addWidget(legend)

    def _on_button_toggled(self, btn_id: str, is_enabled: bool):
        self.disabled_buttons_changed.emit(self._diagram.get_disabled_buttons())

    def _enable_all(self):
        self._diagram.set_disabled_buttons(set())
        self.disabled_buttons_changed.emit(set())

    def _disable_all(self):
        self._diagram.set_disabled_buttons(set(MOUSE_BUTTONS))
        self.disabled_buttons_changed.emit(set(MOUSE_BUTTONS))

    def get_disabled_buttons(self) -> set[str]:
        return self._diagram.get_disabled_buttons()

    def set_disabled_buttons(self, buttons: set[str]):
        self._diagram.set_disabled_buttons(buttons)
