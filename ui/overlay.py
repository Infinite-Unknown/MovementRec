"""Always-on-top floating overlay showing recording state and active playback tracks."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget


ROW_HEIGHT = 24
BASE_HEIGHT = 32
OVERLAY_WIDTH = 220


class OverlayWidget(QWidget):
    """Draggable always-on-top overlay showing recording + playback state."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Recording state
        self._rec_state = "idle"   # "idle" | "recording" | "paused_focus" | "paused_manual"
        self._rec_elapsed = 0.0

        # Playback tracks: list of {slot_id, name, elapsed, total}
        self._tracks: list[dict] = []

        self._drag_pos: QPoint | None = None

        # Pulsing dot
        self._dot_visible = True
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(600)
        self._pulse_timer.timeout.connect(self._toggle_dot)

        self._update_size()

        # Position bottom-right
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 24,
                  screen.bottom() - self.height() - 24)

    # ------------------------------------------------------------------ sizing

    def _update_size(self):
        rows = self._row_count()
        h = max(BASE_HEIGHT, BASE_HEIGHT + (rows - 1) * ROW_HEIGHT) if rows > 0 else BASE_HEIGHT
        self.setFixedSize(OVERLAY_WIDTH, h)

    def _row_count(self) -> int:
        count = 0
        if self._rec_state != "idle":
            count += 1
        count += len(self._tracks)
        if count == 0:
            count = 1  # "Idle" row
        return count

    # ------------------------------------------------------------------ state

    def set_recording_state(self, state: str, elapsed: float = 0.0):
        self._rec_state = state
        self._rec_elapsed = elapsed
        self._update_pulse()
        self._update_size()
        self.update()

    def set_playback_track(self, slot_id: str, name: str, elapsed: float, total: float):
        for t in self._tracks:
            if t["slot_id"] == slot_id:
                t["name"] = name
                t["elapsed"] = elapsed
                t["total"] = total
                self.update()
                return
        self._tracks.append({"slot_id": slot_id, "name": name,
                             "elapsed": elapsed, "total": total})
        self._update_pulse()
        self._update_size()
        self.update()

    def clear_playback_track(self, slot_id: str):
        self._tracks = [t for t in self._tracks if t["slot_id"] != slot_id]
        self._update_pulse()
        self._update_size()
        self.update()

    def clear_all_tracks(self):
        self._tracks.clear()
        self._update_pulse()
        self._update_size()
        self.update()

    def _update_pulse(self):
        active = self._rec_state in ("recording",) or len(self._tracks) > 0
        if active:
            self._dot_visible = True
            if not self._pulse_timer.isActive():
                self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
            self._dot_visible = True

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Background pill
        bg = QColor("#1E1E1E")
        bg.setAlpha(220)
        path = QPainterPath()
        radius = min(h / 2, 16)
        path.addRoundedRect(0, 0, w, h, radius, radius)
        p.fillPath(path, QBrush(bg))

        # Border
        border_color = self._border_color()
        p.setPen(QPen(border_color, 1.5))
        p.drawPath(path)

        # Draw rows
        y = (BASE_HEIGHT - ROW_HEIGHT) // 2  # center first row vertically in base height
        if self._rec_state == "idle" and not self._tracks:
            self._draw_row(p, y, "#555555", "Idle", "", show_dot=False)
        else:
            if self._rec_state != "idle":
                rec_color, rec_label = self._rec_display()
                time_str = self._fmt(self._rec_elapsed)
                self._draw_row(p, y, rec_color, rec_label, time_str,
                               show_dot=self._dot_visible and self._rec_state == "recording")
                y += ROW_HEIGHT

            for t in self._tracks:
                pct_str = self._fmt(t["elapsed"]) + "/" + self._fmt(t["total"])
                name = t["name"]
                if len(name) > 14:
                    name = name[:13] + "\u2026"
                self._draw_row(p, y, "#00B4D8", name, pct_str,
                               show_dot=self._dot_visible)
                y += ROW_HEIGHT

        p.end()

    def _draw_row(self, p: QPainter, y: int, color_hex: str, label: str,
                  time_str: str, show_dot: bool):
        accent = QColor(color_hex)
        dot_x = 14
        cy = y + ROW_HEIGHT // 2

        # Dot
        if show_dot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(accent))
            p.drawEllipse(QPoint(dot_x, cy), 3, 3)

        # Label
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(accent)
        p.drawText(dot_x + 10, y, 120, ROW_HEIGHT,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

        # Time
        if time_str:
            tfont = QFont("Segoe UI", 8)
            p.setFont(tfont)
            p.setPen(QColor("#AAA"))
            p.drawText(self.width() - 80, y, 72, ROW_HEIGHT,
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, time_str)

    def _border_color(self) -> QColor:
        if self._rec_state == "recording":
            return QColor("#E81123")
        if self._rec_state in ("paused_focus", "paused_manual"):
            return QColor("#FF8C00")
        if self._tracks:
            return QColor("#00B4D8")
        return QColor("#555555")

    def _rec_display(self) -> tuple[str, str]:
        if self._rec_state == "recording":
            return "#E81123", "REC"
        if self._rec_state == "paused_focus":
            return "#FF8C00", "PAUSED"
        if self._rec_state == "paused_manual":
            return "#FFB900", "PAUSED"
        return "#555555", "Idle"

    @staticmethod
    def _fmt(seconds: float) -> str:
        m = int(seconds) // 60
        s = seconds - m * 60
        return f"{m}:{s:04.1f}"

    # ------------------------------------------------------------------ drag

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _toggle_dot(self):
        self._dot_visible = not self._dot_visible
        self.update()
