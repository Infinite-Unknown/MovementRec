"""Main application window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pynput import keyboard as kb

from core.input_recorder import InputRecorder
from core.models import Recording, Settings
from core.screenshot import capture_window_thumbnail
from core.window_monitor import WindowMonitor

from .app_selector import AppSelector
from .keybind_dialog import KeybindDialog, KeyCaptureEdit, keybind_to_pynput_str
from .keyboard_widget import KeyboardWidget
from .mouse_widget import MouseWidget
from .overlay import OverlayWidget
from .playback_tab import PlaybackTab
from .recording_list import RecordingList
from .save_dialog import SaveDialog


class RecorderState:
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED_FOCUS = "paused_focus"
    PAUSED_MANUAL = "paused_manual"


class _HotkeyBridge(QObject):
    """Lives on the main thread. Pynput callbacks emit these signals;
    Qt automatically queues them onto the main event loop."""
    start_stop = Signal()
    pause_resume = Signal()


STYLE_SHEET = """
* {
    color: #E0E0E0;
    font-family: "Segoe UI", sans-serif;
}
QMainWindow {
    background-color: #1E1E1E;
}
QToolBar {
    background-color: #2D2D2D;
    border-bottom: 1px solid #3E3E3E;
    spacing: 6px;
    padding: 6px;
}
QToolBar QPushButton {
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: bold;
    background-color: #3C3C3C;
    color: #E0E0E0;
    min-width: 70px;
}
QToolBar QPushButton:hover {
    background-color: #4A4A4A;
}
QToolBar QPushButton:disabled {
    background-color: #2A2A2A;
    color: #666;
    border-color: #444;
}
QPushButton#recordBtn {
    background-color: #0078D4;
    color: white;
    border-color: #005A9E;
}
QPushButton#recordBtn:hover {
    background-color: #1A8AE0;
}
QPushButton#recordBtn[recording="true"] {
    background-color: #E81123;
    border-color: #C50F1F;
}
QPushButton#recordBtn[recording="true"]:hover {
    background-color: #FF2D3B;
}
QPushButton#pauseBtn {
    background-color: #CA8A04;
    color: white;
    border-color: #A16C03;
}
QPushButton#pauseBtn:hover {
    background-color: #E09D05;
}
QStatusBar {
    background-color: #007ACC;
    border-top: none;
    font-size: 11px;
    color: white;
}
QStatusBar QLabel {
    color: white;
}
QTabWidget::pane {
    border: 1px solid #3E3E3E;
    background: #252526;
    border-top: 2px solid #007ACC;
}
QTabBar::tab {
    padding: 10px 24px;
    border: none;
    background: #2D2D2D;
    color: #888;
    font-size: 12px;
    font-weight: bold;
    min-width: 100px;
}
QTabBar::tab:selected {
    background: #252526;
    color: #FFFFFF;
    border-top: 2px solid #007ACC;
}
QTabBar::tab:hover {
    background: #353535;
    color: #CCC;
}
QMenuBar {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border-bottom: 1px solid #3E3E3E;
}
QMenuBar::item:selected {
    background-color: #094771;
}
QMenu {
    background-color: #2D2D2D;
    color: #E0E0E0;
    border: 1px solid #3E3E3E;
}
QMenu::item:selected {
    background-color: #094771;
}
QComboBox {
    background-color: #3C3C3C;
    color: #E0E0E0;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}
QComboBox:hover {
    border-color: #0078D4;
}
QComboBox QAbstractItemView {
    background-color: #2D2D2D;
    color: #E0E0E0;
    selection-background-color: #094771;
    border: 1px solid #3E3E3E;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QListWidget {
    background-color: #252526;
    color: #E0E0E0;
    border: 1px solid #3E3E3E;
    border-radius: 4px;
    font-size: 11px;
}
QListWidget::item {
    padding: 6px;
    border-bottom: 1px solid #333;
}
QListWidget::item:selected {
    background-color: #094771;
}
QListWidget::item:hover {
    background-color: #2A2D2E;
}
QGroupBox {
    border: 1px solid #3E3E3E;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-size: 12px;
    font-weight: bold;
    color: #CCC;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #0078D4;
}
QSpinBox {
    background-color: #3C3C3C;
    color: #E0E0E0;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 4px;
}
QMessageBox {
    background-color: #2D2D2D;
}
QMessageBox QLabel {
    color: #E0E0E0;
}
QDialog {
    background-color: #2D2D2D;
    color: #E0E0E0;
}
QLineEdit {
    background-color: #3C3C3C;
    color: #E0E0E0;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit:focus {
    border-color: #0078D4;
}
QCheckBox {
    color: #E0E0E0;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #555;
    border-radius: 3px;
    background-color: #3C3C3C;
}
QCheckBox::indicator:checked {
    background-color: #0078D4;
    border-color: #0078D4;
}
"""


class SettingsTab(QWidget):
    """Settings tab — hotkeys, recording options, config save/load, and help."""

    def __init__(self, settings: Settings, config_path: Path, parent=None):
        super().__init__(parent)
        self._settings = settings
        self._config_path = config_path
        self._on_keybinds_changed = None  # callback set by MainWindow
        self._on_interval_changed = None  # callback set by MainWindow
        self._dirty = False

        # Auto-save debounce timer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1500)  # 1.5s after last change
        self._autosave_timer.timeout.connect(self._do_save)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Top save bar ----
        save_bar = QWidget()
        save_bar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3E3E3E;")
        save_bar_layout = QHBoxLayout(save_bar)
        save_bar_layout.setContentsMargins(16, 10, 16, 10)

        self._save_status = QLabel("No changes")
        self._save_status.setStyleSheet("color: #888; font-size: 11px;")
        save_bar_layout.addWidget(self._save_status)

        self._autosave_cb = QCheckBox("Auto-save")
        self._autosave_cb.setChecked(settings.keybinds.get("autosave_enabled", False))
        self._autosave_cb.setToolTip("Automatically save config 1.5s after any change")
        self._autosave_cb.toggled.connect(self._on_autosave_toggled)
        save_bar_layout.addWidget(self._autosave_cb)

        self._config_path_label = QLabel(f"Config: {config_path}")
        self._config_path_label.setStyleSheet("color: #555; font-size: 10px;")
        save_bar_layout.addWidget(self._config_path_label, 1)

        self._save_btn = QPushButton("Save Config")
        self._save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4; color: white;
                border: none; border-radius: 4px;
                padding: 6px 18px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1A8AE0; }
            QPushButton:disabled { background-color: #333; color: #666; }
        """)
        self._save_btn.clicked.connect(self._do_save)
        save_bar_layout.addWidget(self._save_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3C3C3C; color: #E0E0E0;
                border: 1px solid #555; border-radius: 4px;
                padding: 6px 18px; font-size: 11px;
            }
            QPushButton:hover { background-color: #4A4A4A; }
        """)
        reset_btn.clicked.connect(self._reset_defaults)
        save_bar_layout.addWidget(reset_btn)

        outer.addWidget(save_bar)

        # ---- Scrollable content ----
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        # Two-column layout for settings groups
        cols = QHBoxLayout()
        cols.setSpacing(20)
        layout.addLayout(cols)

        # Left column
        left_col = QVBoxLayout()
        left_col.setSpacing(20)

        # --- Hotkey Settings ---
        hotkey_group = QGroupBox("Hotkey Settings")
        hotkey_layout = QFormLayout(hotkey_group)
        hotkey_layout.setSpacing(14)
        hotkey_layout.setContentsMargins(16, 28, 16, 16)
        hotkey_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._start_stop_edit = KeyCaptureEdit(settings.keybinds.get("start_stop", "F9"))
        self._start_stop_edit.key_captured.connect(self._on_key_changed)
        hotkey_layout.addRow("Start / Stop Recording:", self._start_stop_edit)

        self._pause_resume_edit = KeyCaptureEdit(settings.keybinds.get("pause_resume", "F10"))
        self._pause_resume_edit.key_captured.connect(self._on_key_changed)
        hotkey_layout.addRow("Pause / Resume:", self._pause_resume_edit)

        hotkey_note = QLabel("Click a field then press any key to assign it.")
        hotkey_note.setStyleSheet("color: #777; font-size: 10px; margin-top: 4px;")
        hotkey_layout.addRow("", hotkey_note)

        left_col.addWidget(hotkey_group)

        # --- Recording Options ---
        rec_group = QGroupBox("Recording Options")
        rec_layout = QFormLayout(rec_group)
        rec_layout.setSpacing(14)
        rec_layout.setContentsMargins(16, 28, 16, 16)
        rec_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._move_interval = QSpinBox()
        self._move_interval.setRange(1, 100)
        self._move_interval.setValue(settings.mouse_move_interval_ms)
        self._move_interval.setSuffix(" ms")
        self._move_interval.setFixedWidth(100)
        self._move_interval.setToolTip(
            "Minimum time between mouse move events.\n"
            "Lower = more precise playback, larger files.\n"
            "Higher = smoother but less accurate."
        )
        self._move_interval.valueChanged.connect(self._mark_dirty)
        rec_layout.addRow("Mouse move throttle:", self._move_interval)

        interval_note = QLabel("8 ms ≈ 125 events/sec  |  16 ms ≈ 60 events/sec")
        interval_note.setStyleSheet("color: #777; font-size: 10px;")
        rec_layout.addRow("", interval_note)

        left_col.addWidget(rec_group)
        left_col.addStretch()
        cols.addLayout(left_col)

        # Right column
        right_col = QVBoxLayout()
        right_col.setSpacing(20)

        # --- How It Works ---
        info_group = QGroupBox("Quick Start Guide")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(16, 28, 16, 16)
        steps = [
            ("1", "Select the target window from the toolbar dropdown."),
            ("2", "In the Keyboard / Mouse tabs, click keys to enable them (green = recorded)."),
            ("3", "Press Record or the hotkey to start. Recording pauses automatically when you switch away."),
            ("4", "Press Stop to save. Optionally include a screenshot preview."),
            ("5", "Find your recordings in the Recordings tab."),
        ]
        for num, text in steps:
            row = QHBoxLayout()
            num_label = QLabel(num)
            num_label.setStyleSheet(
                "background-color: #0078D4; color: white; border-radius: 10px;"
                "min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px;"
                "font-size: 10px; font-weight: bold; qproperty-alignment: AlignCenter;"
            )
            row.addWidget(num_label)
            step_label = QLabel(text)
            step_label.setStyleSheet("color: #BBB; font-size: 11px;")
            step_label.setWordWrap(True)
            row.addWidget(step_label, 1)
            info_layout.addLayout(row)

        right_col.addWidget(info_group)

        # --- Config Info ---
        config_group = QGroupBox("Config Persistence")
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(16, 28, 16, 16)
        config_layout.setSpacing(8)

        self._last_saved_label = QLabel()
        self._last_saved_label.setStyleSheet("color: #AAA; font-size: 11px;")
        self._update_last_saved_label()
        config_layout.addWidget(self._last_saved_label)

        config_info = QLabel(
            "Enable auto-save to persist changes 1.5s after edits.\n"
            "Enabled keys, hotkeys, and options are all persisted."
        )
        config_info.setStyleSheet("color: #777; font-size: 10px;")
        config_layout.addWidget(config_info)

        right_col.addWidget(config_group)
        right_col.addStretch()
        cols.addLayout(right_col)

        outer.addWidget(content)

        # Reflect initial save state
        if settings.last_saved:
            self._set_saved_status()

    def _on_autosave_toggled(self, checked: bool):
        self._settings.keybinds["autosave_enabled"] = checked
        if not checked:
            self._autosave_timer.stop()

    def _mark_dirty(self, *_):
        """Called on any setting change — triggers auto-save if enabled."""
        self._dirty = True
        self._save_status.setText("Unsaved changes...")
        self._save_status.setStyleSheet("color: #FFD93D; font-size: 11px; font-weight: bold;")
        if self._autosave_cb.isChecked():
            self._autosave_timer.start()

    def _do_save(self):
        """Flush current settings to disk."""
        # Collect latest values into settings object
        self._settings.keybinds["start_stop"] = self._start_stop_edit.captured_key() or "F9"
        self._settings.keybinds["pause_resume"] = self._pause_resume_edit.captured_key() or "F10"
        self._settings.mouse_move_interval_ms = self._move_interval.value()
        self._settings.save(self._config_path)
        self._dirty = False
        self._set_saved_status()
        self._update_last_saved_label()
        if self._on_interval_changed:
            self._on_interval_changed(self._move_interval.value())

    def _set_saved_status(self):
        self._save_status.setText("Saved")
        self._save_status.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
        # Fade back to neutral after 3s
        QTimer.singleShot(3000, self._clear_saved_status)

    def _clear_saved_status(self):
        if not self._dirty:
            self._save_status.setText("No changes")
            self._save_status.setStyleSheet("color: #888; font-size: 11px;")

    def _update_last_saved_label(self):
        ts = self._settings.last_saved
        if ts:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ts)
                friendly = dt.strftime("%Y-%m-%d  %H:%M:%S")
                self._last_saved_label.setText(f"Last saved:  {friendly}")
            except ValueError:
                self._last_saved_label.setText(f"Last saved:  {ts}")
        else:
            self._last_saved_label.setText("Last saved:  Never (new config)")

    def _reset_defaults(self):
        self._start_stop_edit.setText("F9")
        self._start_stop_edit._captured_key = "F9"
        self._pause_resume_edit.setText("F10")
        self._pause_resume_edit._captured_key = "F10"
        self._move_interval.setValue(8)
        self._on_key_changed("F9")

    def _on_key_changed(self, key_name: str):
        self._mark_dirty()
        if self._on_keybinds_changed:
            self._on_keybinds_changed()

    def get_move_interval(self) -> int:
        return self._move_interval.value()

    def set_keybinds_callback(self, callback):
        self._on_keybinds_changed = callback

    def set_interval_callback(self, callback):
        self._on_interval_changed = callback

    def mark_key_config_dirty(self):
        """Called when keyboard/mouse key selection changes."""
        self._mark_dirty()


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, base_dir: Path):
        super().__init__()
        self._settings = settings
        self._base_dir = base_dir
        self._config_path = base_dir / "settings.json"
        self._state = RecorderState.IDLE
        self._event_count = 0

        self.setWindowTitle("MovementRec - Input Recorder")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STYLE_SHEET)

        # Core components
        self._window_monitor = WindowMonitor(self)
        self._recorder = InputRecorder(self)

        # Apply settings
        self._recorder.mouse_move_interval_ms = settings.mouse_move_interval_ms
        recordings_path = base_dir / settings.recordings_dir
        recordings_path.mkdir(parents=True, exist_ok=True)

        self._preview_bytes: bytes | None = None  # captured at recording start

        # Bridge for thread-safe hotkey → main-thread dispatch
        self._hotkey_bridge = _HotkeyBridge()
        self._hotkey_bridge.start_stop.connect(self._toggle_recording)
        self._hotkey_bridge.pause_resume.connect(self._toggle_pause)

        self._build_ui(recordings_path)
        self._connect_signals()
        self._setup_global_hotkeys()

        # Apply saved key config. key_config_saved=True means the user has
        # explicitly saved at least once, so we trust disabled_keys even if empty.
        if settings.key_config_saved:
            saved_kb = set(settings.disabled_keys.get("keyboard", []))
            saved_mouse = set(settings.disabled_keys.get("mouse", []))
            self._keyboard_widget.set_disabled_keys(saved_kb)
            self._mouse_widget.set_disabled_buttons(saved_mouse)
        # else: widgets default to all-disabled (first run)
        self._sync_disabled_keys()

        # Timer for elapsed time display
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(100)
        self._elapsed_timer.timeout.connect(self._update_elapsed)

    def _build_ui(self, recordings_path: Path):
        # --- Toolbar (stays on top: app selector + record/pause) ---
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._app_selector = AppSelector(self._window_monitor)
        toolbar.addWidget(self._app_selector)
        toolbar.addSeparator()

        self._record_btn = QPushButton("Record")
        self._record_btn.setObjectName("recordBtn")
        self._record_btn.setProperty("recording", False)
        self._record_btn.clicked.connect(self._toggle_recording)
        toolbar.addWidget(self._record_btn)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setObjectName("pauseBtn")
        self._pause_btn.setEnabled(False)
        self._pause_btn.clicked.connect(self._toggle_pause)
        toolbar.addWidget(self._pause_btn)

        # --- Central: Full-width tab widget ---
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        # Tab 1: Keyboard
        self._keyboard_widget = KeyboardWidget()
        self._tabs.addTab(self._keyboard_widget, "Keyboard")

        # Tab 2: Mouse
        self._mouse_widget = MouseWidget()
        self._tabs.addTab(self._mouse_widget, "Mouse")

        # Tab 3: Recordings
        self._recording_list = RecordingList(str(recordings_path))
        self._tabs.addTab(self._recording_list, "Recordings")

        # Tab 4: Playback
        self._playback_tab = PlaybackTab(str(recordings_path), self._settings)
        self._playback_tab.playback_config_changed.connect(self._on_playback_config_changed)
        self._playback_tab.manager.session_started.connect(self._on_playback_session_started)
        self._playback_tab.manager.session_stopped.connect(self._on_playback_session_stopped)
        self._playback_tab.manager.session_progress.connect(self._on_playback_session_progress)
        self._playback_tab.manager.all_stopped.connect(self._on_all_playback_stopped)
        self._tabs.addTab(self._playback_tab, "Playback")

        # Tab 5: Settings
        self._settings_tab = SettingsTab(self._settings, self._config_path)
        self._settings_tab.set_keybinds_callback(self._on_keybinds_changed)
        self._settings_tab.set_interval_callback(self._on_interval_changed)
        self._tabs.addTab(self._settings_tab, "Settings")

        # --- Always-on-top overlay ---
        self._overlay = OverlayWidget()
        self._overlay.show()

        # --- Status Bar ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._state_label = QLabel("Idle")
        self._state_label.setStyleSheet("font-weight: bold; padding: 0 8px; color: white;")
        self._status_bar.addWidget(self._state_label)

        self._event_label = QLabel("Events: 0")
        self._status_bar.addWidget(self._event_label)

        self._elapsed_label = QLabel("Time: 0.0s")
        self._status_bar.addWidget(self._elapsed_label)

        self._hotkey_label = QLabel()
        self._update_hotkey_label()
        self._status_bar.addPermanentWidget(self._hotkey_label)

    def _connect_signals(self):
        self._app_selector.window_selected.connect(self._on_window_selected)
        self._window_monitor.focus_gained.connect(self._on_focus_gained)
        self._window_monitor.focus_lost.connect(self._on_focus_lost)
        self._recorder.event_captured.connect(self._on_event_captured)
        self._keyboard_widget.disabled_keys_changed.connect(self._on_key_filter_changed)
        self._mouse_widget.disabled_buttons_changed.connect(self._on_key_filter_changed)
        self._recording_list.recording_deleted.connect(self._playback_tab.refresh_recordings)

    def _on_key_filter_changed(self, _=None):
        """Called when keyboard or mouse key toggles change."""
        self._sync_disabled_keys()
        # Notify settings tab to trigger auto-save
        self._settings_tab.mark_key_config_dirty()

    def _sync_disabled_keys(self):
        kb_disabled = self._keyboard_widget.get_disabled_keys()
        mouse_disabled = self._mouse_widget.get_disabled_buttons()
        self._recorder.set_disabled_keys(kb_disabled, mouse_disabled)
        self._settings.disabled_keys["keyboard"] = list(kb_disabled)
        self._settings.disabled_keys["mouse"] = list(mouse_disabled)
        self._settings.key_config_saved = True  # user has made a deliberate choice

    # --- Global Hotkeys ---

    def _setup_global_hotkeys(self):
        self._stop_global_hotkeys()
        binds = self._settings.keybinds
        hotkey_map = {}

        start_stop_key = keybind_to_pynput_str(binds.get("start_stop", "F9"))
        pause_key = keybind_to_pynput_str(binds.get("pause_resume", "F10"))

        hotkey_map[start_stop_key] = self._hotkey_toggle_recording
        hotkey_map[pause_key] = self._hotkey_toggle_pause

        try:
            self._global_hotkey_listener = kb.GlobalHotKeys(hotkey_map)
            self._global_hotkey_listener.daemon = True
            self._global_hotkey_listener.start()
        except Exception as e:
            print(f"Failed to register global hotkeys: {e}")
            self._global_hotkey_listener = None

    def _stop_global_hotkeys(self):
        listener = getattr(self, "_global_hotkey_listener", None)
        if listener:
            listener.stop()
            self._global_hotkey_listener = None

    def _hotkey_toggle_recording(self):
        # Called from pynput thread while the TARGET APP is still focused.
        # Capture screenshot here, before anything shifts focus.
        if self._state == RecorderState.IDLE:
            hwnd = self._app_selector.selected_hwnd()
            self._preview_bytes = capture_window_thumbnail(hwnd) if hwnd else None
        # Signal emission is thread-safe; Qt queues it on the main event loop.
        self._hotkey_bridge.start_stop.emit()

    def _hotkey_toggle_pause(self):
        self._hotkey_bridge.pause_resume.emit()

    # --- Window Selection ---

    def _on_window_selected(self, hwnd: int, exe: str):
        self._window_monitor.set_target(hwnd, exe)
        self._settings.last_target_window_exe = exe

    # --- Recording Control ---

    @Slot()
    def _toggle_recording(self):
        if self._state == RecorderState.IDLE:
            self._start_recording()
        else:
            self._stop_recording()

    @Slot()
    def _toggle_pause(self):
        if self._state == RecorderState.RECORDING:
            self._recorder.pause()
            self._set_state(RecorderState.PAUSED_MANUAL)
        elif self._state == RecorderState.PAUSED_MANUAL:
            self._recorder.resume()
            self._set_state(RecorderState.RECORDING)

    def _start_recording(self):
        if self._app_selector.selected_hwnd() is None:
            QMessageBox.warning(self, "No Window Selected",
                                "Please select a target window before recording.")
            return

        self._event_count = 0
        self._recorder.mouse_move_interval_ms = self._settings_tab.get_move_interval()
        self._sync_disabled_keys()
        # _preview_bytes pre-filled by _hotkey_toggle_recording while target was focused.
        # Stays None when started via UI button (no screenshot in that case).

        self._recorder.start()
        self._window_monitor.start_monitoring()

        if self._window_monitor.is_target_focused():
            self._set_state(RecorderState.RECORDING)
        else:
            self._recorder.pause()
            self._set_state(RecorderState.PAUSED_FOCUS)

        self._elapsed_timer.start()

    def _stop_recording(self):
        self._elapsed_timer.stop()
        self._window_monitor.stop_monitoring()
        events = self._recorder.stop()
        self._set_state(RecorderState.IDLE)

        if not events:
            QMessageBox.information(self, "Empty Recording", "No events were captured.")
            return

        dlg = SaveDialog(preview_bytes=self._preview_bytes, parent=self)
        if dlg.exec() == SaveDialog.DialogCode.Accepted:
            name = dlg.recording_name()
            if not name:
                return
            rec = Recording(
                name=name,
                created=datetime.now().isoformat(),
                duration_seconds=self._recorder.elapsed if events else 0,
                target_window_title=self._app_selector.selected_title(),
                target_window_exe=self._app_selector.selected_exe(),
                has_preview=dlg.include_screenshot(),
                events=events,
            )
            rec_dir = self._base_dir / self._settings.recordings_dir
            rec.save(rec_dir, dlg.preview_bytes())
            self._recording_list.refresh()
            self._playback_tab.refresh_recordings()
            # Switch to recordings tab to show the saved item
            self._tabs.setCurrentWidget(self._recording_list)

        self._preview_bytes = None  # clear for next recording

    # --- Focus Signals ---

    @Slot()
    def _on_focus_gained(self):
        if self._state == RecorderState.PAUSED_FOCUS:
            self._recorder.resume()
            self._set_state(RecorderState.RECORDING)

    @Slot()
    def _on_focus_lost(self):
        if self._state == RecorderState.RECORDING:
            self._recorder.pause()
            self._set_state(RecorderState.PAUSED_FOCUS)

    # --- Event Capture ---

    @Slot(dict)
    def _on_event_captured(self, event: dict):
        self._event_count += 1
        self._event_label.setText(f"Events: {self._event_count}")

    # --- State Management ---

    def _set_state(self, state: str):
        self._state = state

        state_display = {
            RecorderState.IDLE: ("Idle", "#FFFFFF"),
            RecorderState.RECORDING: ("Recording...", "#FF6B6B"),
            RecorderState.PAUSED_FOCUS: ("Paused (unfocused)", "#FFB347"),
            RecorderState.PAUSED_MANUAL: ("Paused (manual)", "#FFD93D"),
        }
        text, color = state_display.get(state, ("Unknown", "#FFFFFF"))
        self._state_label.setText(text)
        self._state_label.setStyleSheet(f"font-weight: bold; padding: 0 8px; color: {color};")

        # Drive the overlay
        self._overlay.set_recording_state(state, self._recorder.elapsed if state != RecorderState.IDLE else 0)

        is_recording = state != RecorderState.IDLE
        self._record_btn.setText("Stop" if is_recording else "Record")
        self._record_btn.setProperty("recording", is_recording)
        self._record_btn.style().unpolish(self._record_btn)
        self._record_btn.style().polish(self._record_btn)

        self._pause_btn.setEnabled(state in (RecorderState.RECORDING, RecorderState.PAUSED_MANUAL))
        self._pause_btn.setText("Resume" if state == RecorderState.PAUSED_MANUAL else "Pause")

        self._app_selector.setEnabled(not is_recording)

        if state == RecorderState.IDLE:
            self._event_label.setText("Events: 0")
            self._elapsed_label.setText("Time: 0.0s")

    def _update_elapsed(self):
        elapsed = self._recorder.elapsed
        self._elapsed_label.setText(f"Time: {elapsed:.1f}s")
        self._overlay.set_recording_state(self._state, elapsed)

    def _update_hotkey_label(self):
        binds = self._settings.keybinds
        self._hotkey_label.setText(
            f"Start/Stop: {binds.get('start_stop', 'F9')}  |  "
            f"Pause: {binds.get('pause_resume', 'F10')}"
        )

    def _on_keybinds_changed(self):
        # Re-read keybinds from settings (already updated by SettingsTab._do_save)
        self._setup_global_hotkeys()
        self._update_hotkey_label()

    def _on_interval_changed(self, value: int):
        self._recorder.mouse_move_interval_ms = value

    def _on_playback_config_changed(self):
        self._settings.save(self._config_path)

    @Slot(str, str, float)
    def _on_playback_session_started(self, slot_id: str, name: str, duration: float):
        self._overlay.set_playback_track(slot_id, name, 0.0, duration)

    @Slot(str)
    def _on_playback_session_stopped(self, slot_id: str):
        self._overlay.clear_playback_track(slot_id)

    @Slot(str, float)
    def _on_playback_session_progress(self, slot_id: str, pct: float):
        # Find duration from overlay tracks
        for t in self._overlay._tracks:
            if t["slot_id"] == slot_id:
                self._overlay.set_playback_track(slot_id, t["name"], pct * t["total"], t["total"])
                break

    @Slot()
    def _on_all_playback_stopped(self):
        self._overlay.clear_all_tracks()

    # --- Cleanup ---

    def closeEvent(self, event):
        if self._state != RecorderState.IDLE:
            self._recorder.stop()
            self._window_monitor.stop_monitoring()
            self._elapsed_timer.stop()
        self._overlay.hide()
        self._stop_global_hotkeys()
        self._playback_tab.cleanup()
        # Final save — picks up any pending changes not yet auto-saved
        self._settings.mouse_move_interval_ms = self._settings_tab.get_move_interval()
        self._settings.key_config_saved = True
        self._settings.save(self._config_path)
        super().closeEvent(event)
