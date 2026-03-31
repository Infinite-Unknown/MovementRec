"""Playback tab — profile-based multi-slot playback with per-recording keybinds."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from pynput import keyboard as kb

from core.models import PlaybackSlot, Profile, Recording, Settings
from core.playback import PlaybackManager, load_recording
from .keybind_dialog import KeyCaptureEdit, KEYBIND_TO_PYNPUT


# ------------------------------------------------------------------ styles

_SLOT_FRAME = """
    QFrame#slotFrame {
        background-color: #2A2A2A;
        border: 1px solid #3E3E3E;
        border-radius: 6px;
    }
"""

_ADD_BTN = """
    QPushButton {
        background-color: #3C3C3C; color: #AAA;
        border: 1px dashed #555; border-radius: 6px;
        padding: 10px; font-size: 12px;
    }
    QPushButton:hover { background-color: #4A4A4A; color: #E0E0E0; }
"""

_PLAY_BTN = """
    QPushButton {
        background-color: #0078D4; color: white;
        border: none; border-radius: 4px;
        padding: 4px 12px; font-size: 11px; font-weight: bold;
        min-width: 40px;
    }
    QPushButton:hover { background-color: #1A8AE0; }
    QPushButton:disabled { background-color: #333; color: #666; }
"""

_STOP_BTN = """
    QPushButton {
        background-color: #E81123; color: white;
        border: none; border-radius: 4px;
        padding: 4px 12px; font-size: 11px; font-weight: bold;
        min-width: 40px;
    }
    QPushButton:hover { background-color: #FF2D3B; }
"""

_REMOVE_BTN = """
    QPushButton {
        background-color: transparent; color: #888;
        border: none; font-size: 14px; font-weight: bold;
        padding: 2px 6px;
    }
    QPushButton:hover { color: #FF6B6B; }
"""

_TRACK_FRAME = """
    QFrame#trackFrame {
        background-color: #1A2A3A;
        border: 1px solid #0078D4;
        border-radius: 4px;
    }
"""


def _fix_combo_font(combo: QComboBox):
    """Prevent 'QFont::setPointSize: Point size <= 0' warning on dropdown."""
    font = combo.font()
    if font.pointSize() <= 0:
        font.setPointSize(9)
    combo.view().setFont(font)


def _fmt_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m}:{s:04.1f}"


# ================================================================== SlotWidget

class SlotWidget(QFrame):
    """One playback slot row with recording selector, keybind, speed, etc."""

    changed = Signal()       # any config change
    removed = Signal(object) # self
    play_clicked = Signal(object)  # self
    stop_clicked = Signal(object)  # self

    def __init__(self, recordings_dir: Path, slot: PlaybackSlot, parent=None):
        super().__init__(parent)
        self.setObjectName("slotFrame")
        self.setStyleSheet(_SLOT_FRAME)
        self._recordings_dir = recordings_dir
        self._slot = slot

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(12)

        # Row 1: Recording + Keybind
        row1_widget = QWidget()
        row1_widget.setFixedHeight(32)
        row1 = QHBoxLayout(row1_widget)
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(10)

        lbl_rec = QLabel("Recording:")
        lbl_rec.setFixedWidth(68)
        row1.addWidget(lbl_rec)
        self._rec_combo = QComboBox()
        self._rec_combo.setMinimumWidth(200)
        self._rec_combo.setFixedHeight(28)
        _fix_combo_font(self._rec_combo)
        self._rec_combo.currentIndexChanged.connect(self._on_change)
        row1.addWidget(self._rec_combo, 1)

        lbl_key = QLabel("Key:")
        lbl_key.setFixedWidth(30)
        row1.addWidget(lbl_key)
        self._keybind = KeyCaptureEdit(slot.keybind)
        self._keybind.setStyleSheet("""
            QLineEdit {
                border: 1px solid #0078D4; border-radius: 3px;
                padding: 2px; font-size: 11px; font-weight: bold;
                background: #3C3C3C; color: #E0E0E0;
                max-height: 22px;
            }
            QLineEdit:focus { border-color: #1A8AE0; background: #2A3A4A; }
        """)
        self._keybind.setFixedSize(70, 26)
        self._keybind.key_captured.connect(lambda _: self._on_change())
        row1.addWidget(self._keybind)

        # Play / Stop stacked in same position
        self._play_btn = QPushButton("Play")
        self._play_btn.setStyleSheet(_PLAY_BTN)
        self._play_btn.clicked.connect(lambda: self.play_clicked.emit(self))

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setStyleSheet(_STOP_BTN)
        self._stop_btn.clicked.connect(lambda: self.stop_clicked.emit(self))

        self._play_stop_stack = QStackedWidget()
        self._play_stop_stack.addWidget(self._play_btn)   # index 0 = Play
        self._play_stop_stack.addWidget(self._stop_btn)    # index 1 = Stop
        self._play_stop_stack.setCurrentIndex(0)
        self._play_stop_stack.setFixedWidth(64)
        row1.addWidget(self._play_stop_stack)

        remove_btn = QPushButton("\u2715")
        remove_btn.setStyleSheet(_REMOVE_BTN)
        remove_btn.setToolTip("Remove slot")
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        row1.addWidget(remove_btn)

        outer.addWidget(row1_widget)

        # Row 2: Speed + Loop + Filter + Priority
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        lbl_speed = QLabel("Speed:")
        lbl_speed.setFixedWidth(42)
        row2.addWidget(lbl_speed)
        self._speed = QDoubleSpinBox()
        self._speed.setRange(0.1, 10.0)
        self._speed.setSingleStep(0.1)
        self._speed.setValue(slot.speed)
        self._speed.setSuffix("x")
        self._speed.setMinimumWidth(80)
        self._speed.setMinimumHeight(28)
        self._speed.valueChanged.connect(lambda _: self._on_change())
        row2.addWidget(self._speed)

        self._loop = QCheckBox("Loop")
        self._loop.setChecked(slot.loop)
        self._loop.toggled.connect(lambda _: self._on_change())
        row2.addWidget(self._loop)

        lbl_filter = QLabel("Filter:")
        lbl_filter.setFixedWidth(36)
        row2.addWidget(lbl_filter)
        self._filter = QComboBox()
        self._filter.setMinimumWidth(120)
        _fix_combo_font(self._filter)
        self._filter.addItem("All Events", "all")
        self._filter.addItem("Mouse Only", "mouse")
        self._filter.addItem("Keyboard Only", "keyboard")
        for i in range(self._filter.count()):
            if self._filter.itemData(i) == slot.event_filter:
                self._filter.setCurrentIndex(i)
                break
        self._filter.currentIndexChanged.connect(lambda _: self._on_change())
        row2.addWidget(self._filter)

        lbl_pri = QLabel("Priority:")
        lbl_pri.setFixedWidth(50)
        row2.addWidget(lbl_pri)
        self._priority = QSpinBox()
        self._priority.setRange(1, 100)
        self._priority.setValue(slot.priority)
        self._priority.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._priority.setMinimumWidth(50)
        self._priority.setMinimumHeight(28)
        self._priority.valueChanged.connect(lambda _: self._on_change())
        row2.addWidget(self._priority)

        row2.addStretch()

        outer.addLayout(row2)

        self._populate_recordings()
        # Select saved recording
        self._select_recording(slot.recording_file)

    def _populate_recordings(self):
        self._rec_combo.blockSignals(True)
        self._rec_combo.clear()
        self._rec_combo.addItem("(none)", "")
        if self._recordings_dir.exists():
            for p in sorted(self._recordings_dir.glob("*.json"),
                            key=lambda f: f.stat().st_mtime, reverse=True):
                meta = Recording.load_metadata(p)
                if meta:
                    self._rec_combo.addItem(
                        f"{meta.name} ({meta.duration_seconds:.1f}s)", p.name)
        self._rec_combo.blockSignals(False)

    def _select_recording(self, filename: str):
        for i in range(self._rec_combo.count()):
            if self._rec_combo.itemData(i) == filename:
                self._rec_combo.setCurrentIndex(i)
                return
        self._rec_combo.setCurrentIndex(0)

    def refresh_recordings(self):
        saved = self.get_slot().recording_file
        self._populate_recordings()
        self._select_recording(saved)

    def get_slot(self) -> PlaybackSlot:
        return PlaybackSlot(
            recording_file=self._rec_combo.currentData() or "",
            keybind=self._keybind.captured_key() or "",
            speed=self._speed.value(),
            loop=self._loop.isChecked(),
            event_filter=self._filter.currentData() or "all",
            priority=self._priority.value(),
        )

    def slot_id(self) -> str:
        return str(id(self))

    def set_playing(self, playing: bool):
        self._play_stop_stack.setCurrentIndex(1 if playing else 0)

    def keybind_str(self) -> str:
        return self._keybind.captured_key() or ""

    def _on_change(self, *_):
        self.changed.emit()


# ================================================================== TrackWidget

class TrackWidget(QFrame):
    """Shows one active playback track with name, timer, progress."""

    stop_requested = Signal(str)  # slot_id

    def __init__(self, slot_id: str, name: str, duration: float, parent=None):
        super().__init__(parent)
        self.setObjectName("trackFrame")
        self.setStyleSheet(_TRACK_FRAME)
        self.setFixedHeight(36)
        self._slot_id = slot_id
        self._duration = duration
        self._elapsed = 0.0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        dot = QLabel("\u25B6")
        dot.setStyleSheet("color: #00B4D8; font-size: 10px;")
        layout.addWidget(dot)

        self._name_label = QLabel(name)
        self._name_label.setStyleSheet("color: #E0E0E0; font-size: 11px; font-weight: bold;")
        self._name_label.setFixedWidth(140)
        layout.addWidget(self._name_label)

        self._time_label = QLabel(_fmt_time(0) + " / " + _fmt_time(duration))
        self._time_label.setStyleSheet("color: #AAA; font-size: 10px;")
        self._time_label.setFixedWidth(100)
        layout.addWidget(self._time_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(8)
        self._progress.setStyleSheet("""
            QProgressBar { background: #1E1E1E; border: 1px solid #333; border-radius: 3px; }
            QProgressBar::chunk { background: #00B4D8; border-radius: 2px; }
        """)
        layout.addWidget(self._progress, 1)

        stop_btn = QPushButton("Stop")
        stop_btn.setStyleSheet("""
            QPushButton { background:#E81123; color:white; border:none; border-radius:3px;
                          padding:2px 8px; font-size:10px; font-weight:bold; }
            QPushButton:hover { background:#FF2D3B; }
        """)
        stop_btn.clicked.connect(lambda: self.stop_requested.emit(self._slot_id))
        layout.addWidget(stop_btn)

    def update_progress(self, pct: float):
        self._elapsed = pct * self._duration
        self._progress.setValue(int(pct * 1000))
        self._time_label.setText(_fmt_time(self._elapsed) + " / " + _fmt_time(self._duration))


# ================================================================== PlaybackTab

class PlaybackTab(QWidget):
    """Tab for profile-based multi-slot playback."""

    playback_config_changed = Signal()

    def __init__(self, recordings_dir: str, settings: Settings, parent=None):
        super().__init__(parent)
        self._recordings_dir = Path(recordings_dir)
        self._settings = settings
        self._manager = PlaybackManager(self)
        self._slot_widgets: list[SlotWidget] = []
        self._track_widgets: dict[str, TrackWidget] = {}
        self._hotkey_listener: Optional[kb.Listener] = None
        # Map SlotWidget id(self) -> SlotWidget for hotkey lookups
        self._slot_by_id: dict[str, SlotWidget] = {}

        self._build_ui()
        self._connect_manager()
        self._load_profile()
        self._start_hotkey_listener()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- Profile bar ----
        profile_bar = QHBoxLayout()
        profile_bar.setSpacing(8)

        profile_bar.addWidget(QLabel("Profile:"))
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(160)
        _fix_combo_font(self._profile_combo)
        self._profile_combo.currentTextChanged.connect(self._on_profile_switched)
        profile_bar.addWidget(self._profile_combo)

        new_btn = QPushButton("+ New")
        new_btn.setStyleSheet("""
            QPushButton { background:#3C3C3C; color:#E0E0E0; border:1px solid #555;
                          border-radius:4px; padding:4px 12px; font-size:11px; }
            QPushButton:hover { background:#4A4A4A; }
        """)
        new_btn.clicked.connect(self._new_profile)
        profile_bar.addWidget(new_btn)

        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet("""
            QPushButton { background:#3C3C3C; color:#E0E0E0; border:1px solid #555;
                          border-radius:4px; padding:4px 12px; font-size:11px; }
            QPushButton:hover { background:#8B0000; color:white; }
        """)
        del_btn.clicked.connect(self._delete_profile)
        profile_bar.addWidget(del_btn)

        rename_btn = QPushButton("Rename")
        rename_btn.setStyleSheet("""
            QPushButton { background:#3C3C3C; color:#E0E0E0; border:1px solid #555;
                          border-radius:4px; padding:4px 12px; font-size:11px; }
            QPushButton:hover { background:#4A4A4A; }
        """)
        rename_btn.clicked.connect(self._rename_profile)
        profile_bar.addWidget(rename_btn)

        profile_bar.addStretch()

        stop_all_btn = QPushButton("Stop All")
        stop_all_btn.setStyleSheet("""
            QPushButton { background:#8B0000; color:white; border:none;
                          border-radius:4px; padding:4px 14px; font-size:11px; font-weight:bold; }
            QPushButton:hover { background:#B22222; }
        """)
        stop_all_btn.clicked.connect(self._manager.stop_all)
        profile_bar.addWidget(stop_all_btn)

        layout.addLayout(profile_bar)

        # ---- Slot list (scrollable) ----
        slots_group = QGroupBox("Playback Slots")
        slots_outer = QVBoxLayout(slots_group)
        slots_outer.setContentsMargins(8, 22, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self._slots_layout = QVBoxLayout(scroll_content)
        self._slots_layout.setContentsMargins(0, 0, 0, 0)
        self._slots_layout.setSpacing(6)
        self._slots_layout.addStretch()

        scroll.setWidget(scroll_content)
        slots_outer.addWidget(scroll)

        add_btn = QPushButton("+ Add Slot")
        add_btn.setStyleSheet(_ADD_BTN)
        add_btn.clicked.connect(self._add_empty_slot)
        slots_outer.addWidget(add_btn)

        layout.addWidget(slots_group, 1)

        # ---- Active playback panel ----
        active_group = QGroupBox("Active Playback")
        self._active_layout = QVBoxLayout(active_group)
        self._active_layout.setContentsMargins(8, 22, 8, 8)
        self._active_layout.setSpacing(4)

        self._no_active_label = QLabel("No active playback")
        self._no_active_label.setStyleSheet("color: #666; font-size: 11px; padding: 8px;")
        self._no_active_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._active_layout.addWidget(self._no_active_label)

        layout.addWidget(active_group)

    def _connect_manager(self):
        self._manager.session_started.connect(self._on_session_started)
        self._manager.session_stopped.connect(self._on_session_stopped)
        self._manager.session_progress.connect(self._on_session_progress)

    # ---------------------------------------------------------------- profiles

    def _refresh_profile_combo(self):
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        for name in sorted(self._settings.profiles.keys()):
            self._profile_combo.addItem(name)
        idx = self._profile_combo.findText(self._settings.active_profile)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)
        self._profile_combo.blockSignals(False)

    def _on_profile_switched(self, name: str):
        if not name:
            return
        self._save_current_profile()
        self._settings.active_profile = name
        self._load_profile()
        self._save_config()

    def _load_profile(self):
        self._refresh_profile_combo()
        # Clear existing slot widgets
        for sw in self._slot_widgets:
            sw.setParent(None)
            sw.deleteLater()
        self._slot_widgets.clear()
        self._slot_by_id.clear()

        profile = self._settings.get_active_profile()
        for slot in profile.slots:
            self._add_slot_widget(slot)

    def _save_current_profile(self):
        profile = Profile(
            name=self._settings.active_profile,
            slots=[sw.get_slot() for sw in self._slot_widgets],
        )
        self._settings.save_profile(profile)

    def _new_profile(self):
        name, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._settings.profiles:
            QMessageBox.warning(self, "Exists", f"Profile '{name}' already exists.")
            return
        self._save_current_profile()
        self._settings.profiles[name] = Profile(name=name).to_dict()
        self._settings.active_profile = name
        self._load_profile()
        self._save_config()

    def _delete_profile(self):
        name = self._settings.active_profile
        if len(self._settings.profiles) <= 1:
            QMessageBox.warning(self, "Cannot Delete", "Must keep at least one profile.")
            return
        reply = QMessageBox.question(self, "Delete Profile",
                                     f"Delete profile '{name}'?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._settings.profiles.pop(name, None)
        self._settings.active_profile = next(iter(self._settings.profiles))
        self._load_profile()
        self._save_config()

    def _rename_profile(self):
        old_name = self._settings.active_profile
        new_name, ok = QInputDialog.getText(self, "Rename Profile",
                                            "New name:", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        if new_name in self._settings.profiles:
            QMessageBox.warning(self, "Exists", f"Profile '{new_name}' already exists.")
            return
        self._save_current_profile()
        data = self._settings.profiles.pop(old_name)
        data["name"] = new_name
        self._settings.profiles[new_name] = data
        self._settings.active_profile = new_name
        self._refresh_profile_combo()
        self._save_config()

    # ---------------------------------------------------------------- slots

    def _add_slot_widget(self, slot: PlaybackSlot):
        sw = SlotWidget(self._recordings_dir, slot, self)
        sw.changed.connect(self._on_slot_changed)
        sw.removed.connect(self._remove_slot)
        sw.play_clicked.connect(self._on_slot_play)
        sw.stop_clicked.connect(self._on_slot_stop)
        self._slot_widgets.append(sw)
        self._slot_by_id[sw.slot_id()] = sw
        # Insert before the stretch
        self._slots_layout.insertWidget(self._slots_layout.count() - 1, sw)

    def _add_empty_slot(self):
        # Auto-assign next available priority
        used = {sw._priority.value() for sw in self._slot_widgets}
        pri = 1
        while pri in used:
            pri += 1
        self._add_slot_widget(PlaybackSlot(priority=pri))
        self._on_slot_changed()

    def _remove_slot(self, sw: SlotWidget):
        sid = sw.slot_id()
        if self._manager.is_playing(sid):
            self._manager.stop(sid)
        self._slot_widgets.remove(sw)
        self._slot_by_id.pop(sid, None)
        sw.setParent(None)
        sw.deleteLater()
        self._on_slot_changed()

    def _on_slot_changed(self, *_):
        self._enforce_unique_priorities()
        self._save_current_profile()
        self._save_config()
        self._restart_hotkey_listener()

    def _enforce_unique_priorities(self):
        """Ensure no two slots share the same priority. Auto-bump duplicates."""
        used: dict[int, SlotWidget] = {}
        for sw in self._slot_widgets:
            pri = sw._priority.value()
            if pri in used:
                # Find next available priority
                new_pri = pri + 1
                while new_pri in used:
                    new_pri += 1
                sw._priority.blockSignals(True)
                sw._priority.setValue(new_pri)
                sw._priority.blockSignals(False)
                pri = new_pri
            used[pri] = sw

    def _on_slot_play(self, sw: SlotWidget):
        self._start_slot(sw)

    def _on_slot_stop(self, sw: SlotWidget):
        self._manager.stop(sw.slot_id())

    def _start_slot(self, sw: SlotWidget):
        slot = sw.get_slot()
        if not slot.recording_file:
            return
        rec_path = self._recordings_dir / slot.recording_file
        if not rec_path.exists():
            return
        try:
            recording = load_recording(rec_path)
        except Exception:
            return
        self._manager.toggle(sw.slot_id(), recording, slot)

    # ---------------------------------------------------------------- hotkey

    def _start_hotkey_listener(self):
        self._stop_hotkey_listener()
        self._hotkey_listener = kb.Listener(
            on_press=self._on_global_press,
        )
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()

    def _stop_hotkey_listener(self):
        if self._hotkey_listener:
            self._hotkey_listener.stop()
            self._hotkey_listener = None

    def _restart_hotkey_listener(self):
        self._start_hotkey_listener()

    def _on_global_press(self, key):
        key_name = self._key_to_name(key)
        if not key_name:
            return
        for sw in self._slot_widgets:
            if sw.keybind_str() and sw.keybind_str() == key_name:
                self._start_slot(sw)

    @staticmethod
    def _key_to_name(key) -> str:
        if hasattr(key, "name"):
            # Map pynput name back to our keybind name
            name = key.name
            # Reverse lookup: pynput "f6" -> "F6"
            for display, pynput_name in KEYBIND_TO_PYNPUT.items():
                if pynput_name == name:
                    return display
            return name.capitalize() if len(name) > 1 else name
        if hasattr(key, "char") and key.char:
            return key.char.upper() if len(key.char) == 1 else key.char
        return ""

    # ---------------------------------------------------------------- manager signals

    @Slot(str, str, float)
    def _on_session_started(self, slot_id: str, name: str, duration: float):
        sw = self._slot_by_id.get(slot_id)
        if sw:
            sw.set_playing(True)

        self._no_active_label.setVisible(False)

        track = TrackWidget(slot_id, name, duration, self)
        track.stop_requested.connect(self._manager.stop)
        self._track_widgets[slot_id] = track
        self._active_layout.addWidget(track)

    @Slot(str)
    def _on_session_stopped(self, slot_id: str):
        sw = self._slot_by_id.get(slot_id)
        if sw:
            sw.set_playing(False)

        track = self._track_widgets.pop(slot_id, None)
        if track:
            track.setParent(None)
            track.deleteLater()

        if not self._track_widgets:
            self._no_active_label.setVisible(True)

    @Slot(str, float)
    def _on_session_progress(self, slot_id: str, pct: float):
        track = self._track_widgets.get(slot_id)
        if track:
            track.update_progress(pct)

    # ---------------------------------------------------------------- public

    def refresh_recordings(self):
        for sw in self._slot_widgets:
            sw.refresh_recordings()

    @property
    def manager(self) -> PlaybackManager:
        return self._manager

    def _save_config(self):
        self.playback_config_changed.emit()

    def cleanup(self):
        self._stop_hotkey_listener()
        self._manager.stop_all()
