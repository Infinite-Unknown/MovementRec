"""Recording list widget with detail/edit panel."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.models import Recording


class RecordingList(QWidget):
    """Shows saved recordings with detail/edit panel."""

    recording_selected = Signal(str)  # path to selected recording JSON
    recording_deleted = Signal()      # emitted after a recording is deleted

    def __init__(self, recordings_dir: str = "recordings", parent=None):
        super().__init__(parent)
        self._recordings_dir = Path(recordings_dir)
        self._current_path: Optional[Path] = None  # currently selected JSON
        self._current_rec: Optional[Recording] = None  # full loaded recording

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # ---- Left: recording list ----
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        header = QLabel("Saved Recordings")
        header.setStyleSheet("font-size: 12px; font-weight: bold; padding: 8px; color: #E0E0E0;")
        left_layout.addWidget(header)

        self._list = QListWidget()
        self._list.setIconSize(QSize(80, 45))
        self._list.setSpacing(2)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list)

        splitter.addWidget(left)

        # ---- Right: detail / edit panel ----
        right = QWidget()
        right.setMinimumWidth(280)
        self._detail_layout = QVBoxLayout(right)
        self._detail_layout.setContentsMargins(12, 8, 12, 8)
        self._detail_layout.setSpacing(12)

        # Preview thumbnail
        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumHeight(120)
        self._preview_label.setStyleSheet(
            "background-color: #1E1E1E; border: 1px solid #3E3E3E; border-radius: 4px;"
        )
        self._detail_layout.addWidget(self._preview_label)

        # Info
        self._info_label = QLabel("Select a recording")
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #BBB; font-size: 11px; line-height: 1.5;")
        self._detail_layout.addWidget(self._info_label)

        # ---- Rename group ----
        rename_group = QGroupBox("Rename")
        rename_layout = QHBoxLayout(rename_group)
        rename_layout.setContentsMargins(10, 22, 10, 10)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Recording name...")
        rename_layout.addWidget(self._name_edit, 1)

        self._rename_btn = QPushButton("Rename")
        self._rename_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; color: white;
                border: none; border-radius: 4px;
                padding: 6px 14px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1A8AE0; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self._rename_btn.clicked.connect(self._do_rename)
        rename_layout.addWidget(self._rename_btn)

        self._detail_layout.addWidget(rename_group)

        # ---- Trim group ----
        trim_group = QGroupBox("Trim")
        trim_layout = QVBoxLayout(trim_group)
        trim_layout.setContentsMargins(10, 22, 10, 10)
        trim_layout.setSpacing(8)

        time_row = QHBoxLayout()
        time_row.setSpacing(8)

        time_row.addWidget(QLabel("Start:"))
        self._trim_start = QDoubleSpinBox()
        self._trim_start.setRange(0, 9999)
        self._trim_start.setDecimals(2)
        self._trim_start.setSuffix(" s")
        self._trim_start.setSingleStep(0.1)
        time_row.addWidget(self._trim_start, 1)

        time_row.addWidget(QLabel("End:"))
        self._trim_end = QDoubleSpinBox()
        self._trim_end.setRange(0, 9999)
        self._trim_end.setDecimals(2)
        self._trim_end.setSuffix(" s")
        self._trim_end.setSingleStep(0.1)
        time_row.addWidget(self._trim_end, 1)

        trim_layout.addLayout(time_row)

        trim_info = QLabel("Keeps events within the time range and re-bases timestamps.")
        trim_info.setStyleSheet("color: #777; font-size: 10px;")
        trim_info.setWordWrap(True)
        trim_layout.addWidget(trim_info)

        trim_btns = QHBoxLayout()
        trim_btns.setSpacing(8)

        self._trim_btn = QPushButton("Trim && Save")
        self._trim_btn.setStyleSheet("""
            QPushButton {
                background-color: #CA8A04; color: white;
                border: none; border-radius: 4px;
                padding: 6px 14px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #E09D05; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self._trim_btn.clicked.connect(self._do_trim)
        trim_btns.addWidget(self._trim_btn)

        self._trim_copy_btn = QPushButton("Trim as Copy")
        self._trim_copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C3C3C; color: #E0E0E0;
                border: 1px solid #555; border-radius: 4px;
                padding: 6px 14px; font-size: 11px;
            }
            QPushButton:hover { background-color: #4A4A4A; }
            QPushButton:disabled { background-color: #2A2A2A; color: #666; }
        """)
        self._trim_copy_btn.clicked.connect(self._do_trim_copy)
        trim_btns.addWidget(self._trim_copy_btn)

        trim_layout.addLayout(trim_btns)
        self._detail_layout.addWidget(trim_group)

        # ---- Delete button ----
        self._delete_btn = QPushButton("Delete Recording")
        self._delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B0000; color: white;
                border: none; border-radius: 4px;
                padding: 8px 16px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #B22222; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self._delete_btn.clicked.connect(self._do_delete)
        self._detail_layout.addWidget(self._delete_btn)

        self._detail_layout.addStretch()

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        # Disable edit controls initially
        self._set_edit_enabled(False)

        self.refresh()

    # ---------------------------------------------------------------- public

    def refresh(self):
        """Scan recordings directory and populate the list."""
        self._list.clear()
        self._clear_detail()
        if not self._recordings_dir.exists():
            return

        json_files = sorted(
            self._recordings_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for json_path in json_files:
            rec = Recording.load_metadata(json_path)
            if rec is None:
                continue

            display = f"{rec.name}\n{rec.created[:10]}  \u2022  {rec.duration_seconds:.1f}s"
            if rec.target_window_exe:
                display += f"  \u2022  {rec.target_window_exe}"

            item = QListWidgetItem()
            item.setText(display)
            item.setData(Qt.ItemDataRole.UserRole, str(json_path))

            png_path = json_path.with_suffix(".png")
            if rec.has_preview and png_path.exists():
                pixmap = QPixmap(str(png_path))
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))

            self._list.addItem(item)

    def set_recordings_dir(self, path: str):
        self._recordings_dir = Path(path)
        self.refresh()

    # ---------------------------------------------------------------- selection

    def _on_selection_changed(self, current: QListWidgetItem, _previous):
        if current is None:
            self._clear_detail()
            return

        json_path = Path(current.data(Qt.ItemDataRole.UserRole))
        self._load_detail(json_path)

    def _load_detail(self, json_path: Path):
        """Load full recording and populate the detail panel."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            rec = Recording.from_dict(data)
        except (json.JSONDecodeError, KeyError, OSError):
            self._clear_detail()
            return

        self._current_path = json_path
        self._current_rec = rec
        self._set_edit_enabled(True)

        # Info
        event_counts = {}
        for ev in rec.events:
            event_counts[ev.type.value] = event_counts.get(ev.type.value, 0) + 1
        counts_str = ", ".join(f"{k}: {v}" for k, v in sorted(event_counts.items()))

        info = (
            f"<b>{rec.name}</b><br>"
            f"Created: {rec.created[:19].replace('T', '  ')}<br>"
            f"Duration: {rec.duration_seconds:.2f}s<br>"
            f"Target: {rec.target_window_exe or 'N/A'}<br>"
            f"Events: {len(rec.events)} total<br>"
            f"<span style='color:#888;'>{counts_str}</span>"
        )
        self._info_label.setText(info)

        # Preview
        png_path = json_path.with_suffix(".png")
        if rec.has_preview and png_path.exists():
            pixmap = QPixmap(str(png_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._preview_label.width() - 4, 160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_label.setPixmap(scaled)
            else:
                self._preview_label.setText("No preview")
        else:
            self._preview_label.clear()
            self._preview_label.setText("No preview")

        # Rename field
        self._name_edit.setText(rec.name)

        # Trim spinboxes
        duration = rec.duration_seconds
        self._trim_start.setRange(0, max(0, duration))
        self._trim_start.setValue(0)
        self._trim_end.setRange(0, max(0, duration))
        self._trim_end.setValue(duration)

    def _clear_detail(self):
        self._current_path = None
        self._current_rec = None
        self._info_label.setText("Select a recording")
        self._preview_label.clear()
        self._preview_label.setText("")
        self._name_edit.clear()
        self._trim_start.setValue(0)
        self._trim_end.setValue(0)
        self._set_edit_enabled(False)

    def _set_edit_enabled(self, enabled: bool):
        self._name_edit.setEnabled(enabled)
        self._rename_btn.setEnabled(enabled)
        self._trim_start.setEnabled(enabled)
        self._trim_end.setEnabled(enabled)
        self._trim_btn.setEnabled(enabled)
        self._trim_copy_btn.setEnabled(enabled)
        self._delete_btn.setEnabled(enabled)

    # ---------------------------------------------------------------- rename

    def _do_rename(self):
        if not self._current_path or not self._current_rec:
            return

        new_name = self._name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Invalid Name", "Name cannot be empty.")
            return

        old_path = self._current_path
        old_png = old_path.with_suffix(".png")

        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in new_name)
        new_json_path = old_path.parent / f"{safe_name}.json"
        new_png_path = old_path.parent / f"{safe_name}.png"

        # Update JSON content
        try:
            with open(old_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["name"] = new_name
            with open(old_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except (json.JSONDecodeError, OSError) as e:
            QMessageBox.warning(self, "Error", f"Failed to update recording: {e}")
            return

        # Rename files if name changed
        if new_json_path != old_path:
            try:
                # Handle collision
                if new_json_path.exists() and new_json_path != old_path:
                    reply = QMessageBox.question(
                        self, "File Exists",
                        f"'{safe_name}.json' already exists. Overwrite?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    new_json_path.unlink()
                    if new_png_path.exists():
                        new_png_path.unlink()

                old_path.rename(new_json_path)
                if old_png.exists():
                    old_png.rename(new_png_path)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Failed to rename file: {e}")
                return

        self.refresh()
        self._select_path(new_json_path)

    # ---------------------------------------------------------------- trim

    def _do_trim(self):
        self._trim_recording(save_as_copy=False)

    def _do_trim_copy(self):
        self._trim_recording(save_as_copy=True)

    def _trim_recording(self, save_as_copy: bool):
        if not self._current_path or not self._current_rec:
            return

        start_t = self._trim_start.value()
        end_t = self._trim_end.value()

        if end_t <= start_t:
            QMessageBox.warning(self, "Invalid Range", "End time must be greater than start time.")
            return

        rec = self._current_rec

        # Filter events within the time range
        trimmed_events = [ev for ev in rec.events if start_t <= ev.t <= end_t]

        if not trimmed_events:
            QMessageBox.warning(self, "No Events", "No events fall within the specified time range.")
            return

        # Re-base timestamps so the first event starts at t=0
        base_t = trimmed_events[0].t
        for ev in trimmed_events:
            ev.t = round(ev.t - base_t, 4)

        new_duration = trimmed_events[-1].t

        if save_as_copy:
            new_name = f"{rec.name} (trimmed)"
            safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in new_name)
            target_path = self._current_path.parent / f"{safe_name}.json"

            # Avoid overwriting
            counter = 1
            while target_path.exists():
                counter += 1
                target_path = self._current_path.parent / f"{safe_name} {counter}.json"
                new_name = f"{rec.name} (trimmed {counter})"
        else:
            new_name = rec.name
            target_path = self._current_path

        # Build trimmed recording
        trimmed_rec = Recording(
            name=new_name,
            created=rec.created,
            duration_seconds=new_duration,
            target_window_title=rec.target_window_title,
            target_window_exe=rec.target_window_exe,
            has_preview=rec.has_preview,
            events=trimmed_events,
        )

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(trimmed_rec.to_dict(), f, indent=2)

            # Copy preview to new file if saving as copy
            if save_as_copy and rec.has_preview:
                src_png = self._current_path.with_suffix(".png")
                dst_png = target_path.with_suffix(".png")
                if src_png.exists():
                    import shutil
                    shutil.copy2(str(src_png), str(dst_png))
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Failed to save trimmed recording: {e}")
            return

        action = "copied" if save_as_copy else "saved"
        QMessageBox.information(
            self, "Trimmed",
            f"Trimmed from {start_t:.2f}s to {end_t:.2f}s\n"
            f"{len(trimmed_events)} events, {new_duration:.2f}s duration\n"
            f"File {action}: {target_path.name}"
        )

        self.refresh()
        self._select_path(target_path)

    # ---------------------------------------------------------------- delete

    def _do_delete(self):
        if not self._current_path:
            return

        reply = QMessageBox.question(
            self, "Delete Recording",
            f"Delete '{self._current_path.stem}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._current_path.unlink(missing_ok=True)
            self._current_path.with_suffix(".png").unlink(missing_ok=True)
        except OSError:
            pass

        self._clear_detail()
        self.refresh()
        self.recording_deleted.emit()

    # ---------------------------------------------------------------- context menu

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if item is None:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("Delete")
        open_folder_action = menu.addAction("Open folder")

        action = menu.exec(self._list.mapToGlobal(pos))
        json_path = Path(item.data(Qt.ItemDataRole.UserRole))

        if action == delete_action:
            reply = QMessageBox.question(
                self, "Delete Recording",
                f"Delete '{json_path.stem}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    json_path.unlink(missing_ok=True)
                    json_path.with_suffix(".png").unlink(missing_ok=True)
                except OSError:
                    pass
                self.refresh()
                self.recording_deleted.emit()
        elif action == open_folder_action:
            os.startfile(str(self._recordings_dir))

    def _on_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.recording_selected.emit(path)

    # ---------------------------------------------------------------- helpers

    def _select_path(self, target_path: Path):
        """Select the list item matching the given path after a refresh."""
        target_str = str(target_path)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == target_str:
                self._list.setCurrentItem(item)
                break
