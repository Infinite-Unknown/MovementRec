"""App/window selector combo box widget."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from core.window_monitor import WindowMonitor, WindowInfo


class AppSelector(QWidget):
    """Combo box for selecting a target window, with refresh button."""

    window_selected = Signal(int, str)  # hwnd, exe_name

    def __init__(self, window_monitor: WindowMonitor, parent=None):
        super().__init__(parent)
        self._monitor = window_monitor

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(300)
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self._combo, 1)

        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.setFixedWidth(80)
        self._refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self._refresh_btn)

        self.refresh()

    def refresh(self):
        """Repopulate the window list."""
        self._combo.blockSignals(True)
        current_hwnd = self.selected_hwnd()
        self._combo.clear()

        self._combo.addItem("-- Select a window --", None)

        windows = self._monitor.list_windows()
        reselect_idx = 0
        for i, w in enumerate(windows):
            self._combo.addItem(w.display_text(), (w.hwnd, w.exe))
            if w.hwnd == current_hwnd:
                reselect_idx = i + 1  # +1 for placeholder

        self._combo.setCurrentIndex(reselect_idx)
        self._combo.blockSignals(False)

    def selected_hwnd(self) -> int | None:
        data = self._combo.currentData()
        if data is None:
            return None
        return data[0]

    def selected_exe(self) -> str:
        data = self._combo.currentData()
        if data is None:
            return ""
        return data[1]

    def selected_title(self) -> str:
        text = self._combo.currentText()
        if text.startswith("--"):
            return ""
        return text

    def _on_selection_changed(self, index):
        data = self._combo.itemData(index)
        if data is not None:
            hwnd, exe = data
            self.window_selected.emit(hwnd, exe)
