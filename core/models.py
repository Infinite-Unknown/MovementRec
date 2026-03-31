"""Data models for recordings, events, and settings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional



class EventType(str, Enum):
    MOUSE_MOVE = "mouse_move"
    MOUSE_MOVE_RELATIVE = "mouse_move_relative"
    MOUSE_BUTTON = "mouse_button"
    KEY = "key"
    SCROLL = "scroll"


@dataclass
class InputEvent:
    type: EventType
    t: float
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None
    key: Optional[str] = None
    vk: Optional[int] = None
    action: Optional[str] = None
    dx: Optional[int] = None
    dy: Optional[int] = None

    def to_dict(self) -> dict:
        d: dict = {"type": self.type.value, "t": round(self.t, 4)}
        for attr in ("x", "y", "button", "key", "vk", "action", "dx", "dy"):
            v = getattr(self, attr)
            if v is not None:
                d[attr] = v
        return d

    @staticmethod
    def from_dict(d: dict) -> InputEvent:
        return InputEvent(
            type=EventType(d["type"]),
            t=d["t"],
            x=d.get("x"),
            y=d.get("y"),
            button=d.get("button"),
            key=d.get("key"),
            vk=d.get("vk"),
            action=d.get("action"),
            dx=d.get("dx"),
            dy=d.get("dy"),
        )


@dataclass
class PlaybackSlot:
    """One recording-to-keybind assignment within a profile."""
    recording_file: str = ""        # filename e.g. "walk.json"
    keybind: str = ""               # e.g. "F6", "" = no hotkey
    speed: float = 1.0
    loop: bool = False
    event_filter: str = "all"       # "all" | "mouse" | "keyboard"
    priority: int = 5               # 1-10

    def to_dict(self) -> dict:
        return {
            "recording_file": self.recording_file,
            "keybind": self.keybind,
            "speed": self.speed,
            "loop": self.loop,
            "event_filter": self.event_filter,
            "priority": self.priority,
        }

    @staticmethod
    def from_dict(d: dict) -> PlaybackSlot:
        return PlaybackSlot(
            recording_file=d.get("recording_file", ""),
            keybind=d.get("keybind", ""),
            speed=d.get("speed", 1.0),
            loop=d.get("loop", False),
            event_filter=d.get("event_filter", "all"),
            priority=d.get("priority", 5),
        )


@dataclass
class Profile:
    """Named collection of playback slots (e.g. per-game config)."""
    name: str
    slots: list[PlaybackSlot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slots": [s.to_dict() for s in self.slots],
        }

    @staticmethod
    def from_dict(d: dict) -> Profile:
        return Profile(
            name=d.get("name", "Default"),
            slots=[PlaybackSlot.from_dict(s) for s in d.get("slots", [])],
        )


@dataclass
class Recording:
    name: str
    created: str
    duration_seconds: float
    target_window_title: str
    target_window_exe: str
    has_preview: bool
    events: list[InputEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "name": self.name,
            "created": self.created,
            "duration_seconds": round(self.duration_seconds, 3),
            "target_window": {
                "title": self.target_window_title,
                "exe": self.target_window_exe,
            },
            "has_preview": self.has_preview,
            "events": [e.to_dict() for e in self.events],
        }

    @staticmethod
    def from_dict(d: dict) -> Recording:
        tw = d.get("target_window", {})
        return Recording(
            name=d["name"],
            created=d["created"],
            duration_seconds=d["duration_seconds"],
            target_window_title=tw.get("title", ""),
            target_window_exe=tw.get("exe", ""),
            has_preview=d.get("has_preview", False),
            events=[InputEvent.from_dict(e) for e in d.get("events", [])],
        )

    @staticmethod
    def load_metadata(path: Path) -> Optional[Recording]:
        """Load recording metadata without loading events (for list display)."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            tw = d.get("target_window", {})
            return Recording(
                name=d["name"],
                created=d["created"],
                duration_seconds=d["duration_seconds"],
                target_window_title=tw.get("title", ""),
                target_window_exe=tw.get("exe", ""),
                has_preview=d.get("has_preview", False),
                events=[],  # Skip loading events for performance
            )
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def save(self, directory: Path, preview_bytes: Optional[bytes] = None) -> Path:
        """Save recording JSON and optional preview PNG to directory."""
        directory.mkdir(parents=True, exist_ok=True)
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in self.name)
        json_path = directory / f"{safe_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        if preview_bytes and self.has_preview:
            png_path = directory / f"{safe_name}.png"
            with open(png_path, "wb") as f:
                f.write(preview_bytes)
        return json_path


DEFAULT_SETTINGS = {
    "keybinds": {
        "start_stop": "F9",
        "pause_resume": "F10",
    },
    "disabled_keys": {
        "keyboard": [],
        "mouse": [],
    },
    "recordings_dir": "recordings",
    "mouse_move_interval_ms": 8,
    "last_target_window_exe": "",
}


@dataclass
class Settings:
    keybinds: dict = field(default_factory=lambda: {
        "start_stop": "F9",
        "pause_resume": "F10",
    })
    disabled_keys: dict = field(default_factory=lambda: {
        "keyboard": [],
        "mouse": [],
    })
    recordings_dir: str = "recordings"
    mouse_move_interval_ms: int = 8
    last_target_window_exe: str = ""
    key_config_saved: bool = False
    last_saved: str = ""
    profiles: dict = field(default_factory=lambda: {
        "Default": Profile(name="Default").to_dict(),
    })
    active_profile: str = "Default"

    def get_active_profile(self) -> Profile:
        d = self.profiles.get(self.active_profile)
        if d is None:
            return Profile(name=self.active_profile)
        return Profile.from_dict(d)

    def save_profile(self, profile: Profile):
        self.profiles[profile.name] = profile.to_dict()

    def to_dict(self) -> dict:
        return {
            "version": 3,
            "keybinds": self.keybinds,
            "disabled_keys": self.disabled_keys,
            "recordings_dir": self.recordings_dir,
            "mouse_move_interval_ms": self.mouse_move_interval_ms,
            "last_target_window_exe": self.last_target_window_exe,
            "key_config_saved": self.key_config_saved,
            "last_saved": self.last_saved,
            "profiles": self.profiles,
            "active_profile": self.active_profile,
        }

    @staticmethod
    def from_dict(d: dict) -> Settings:
        defaults = DEFAULT_SETTINGS
        s = Settings(
            keybinds=d.get("keybinds", defaults["keybinds"]),
            disabled_keys=d.get("disabled_keys", defaults["disabled_keys"]),
            recordings_dir=d.get("recordings_dir", defaults["recordings_dir"]),
            mouse_move_interval_ms=d.get("mouse_move_interval_ms", defaults["mouse_move_interval_ms"]),
            last_target_window_exe=d.get("last_target_window_exe", ""),
            key_config_saved=d.get("key_config_saved", False),
            last_saved=d.get("last_saved", ""),
            profiles=d.get("profiles", {}),
            active_profile=d.get("active_profile", "Default"),
        )
        # Migration: create Default profile if none exist
        if not s.profiles:
            default_profile = Profile(name="Default")
            # Migrate old playback settings into a slot if present
            kb = s.keybinds
            if "playback" in kb:
                slot = PlaybackSlot(
                    keybind=kb.get("playback", "F6"),
                    speed=float(kb.get("playback_speed", "1.0")),
                    loop=kb.get("playback_loop", False),
                )
                default_profile.slots.append(slot)
            s.profiles["Default"] = default_profile.to_dict()
            s.active_profile = "Default"
        return s

    def save(self, path: Path):
        self.last_saved = datetime.now().isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path: Path) -> Settings:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return Settings.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError):
            return Settings()
