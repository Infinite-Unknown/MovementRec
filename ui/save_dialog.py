"""Save recording dialog with optional screenshot preview."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class SaveDialog(QDialog):
    """Dialog for naming and saving a recording."""

    def __init__(
        self,
        preview_bytes: Optional[bytes] = None,
        default_name: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Save Recording")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Recording name
        layout.addWidget(QLabel("Recording name:"))
        self._name_edit = QLineEdit()
        if default_name:
            self._name_edit.setText(default_name)
        else:
            self._name_edit.setText(f"Recording {datetime.now().strftime('%Y-%m-%d %H%M%S')}")
        self._name_edit.selectAll()
        layout.addWidget(self._name_edit)

        # Screenshot checkbox
        self._screenshot_cb = QCheckBox("Include screenshot preview")
        self._screenshot_cb.setChecked(preview_bytes is not None)
        self._screenshot_cb.setEnabled(preview_bytes is not None)
        layout.addWidget(self._screenshot_cb)

        # Preview thumbnail
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("border: 1px solid #555; padding: 4px; color: #AAA; background-color: #252526;")
        self._preview_bytes = preview_bytes

        if preview_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(preview_bytes)
            self._preview_label.setPixmap(
                pixmap.scaled(320, 180, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self._preview_label.setText("No preview available")
            self._preview_label.setMinimumHeight(60)

        layout.addWidget(self._preview_label)

        # Toggle preview visibility
        self._screenshot_cb.toggled.connect(self._preview_label.setVisible)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._name_edit.setFocus()

    def recording_name(self) -> str:
        return self._name_edit.text().strip()

    def include_screenshot(self) -> bool:
        return self._screenshot_cb.isChecked()

    def preview_bytes(self) -> Optional[bytes]:
        if self.include_screenshot() and self._preview_bytes:
            return self._preview_bytes
        return None
