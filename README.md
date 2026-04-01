# MovementRec

A Windows desktop tool for recording and playing back mouse and keyboard input. Designed for automating repetitive input sequences across any application.

## Features

- **Record** mouse movements, clicks, scroll wheel, and keyboard input
- **Playback** recordings with adjustable speed and looping
- **Multiple playback slots** with assignable hotkeys (F-keys)
- **Profile system** for organizing per-app or per-game configurations
- **Target window detection** with auto-pause when the window loses focus
- **Configurable keybinds** for start/stop, pause/resume, and playback
- **Per-key filtering** to exclude specific keys from recording
- **Always-on-top overlay** showing recording and playback state
- **Window screenshots** saved as thumbnails alongside recordings

## Download

Download the latest release from the [Releases](https://github.com/Infinite-Unknown/MovementRec/releases) page.

1. Download `MovementRec_V1.exe` below
2. Extract into a new folder (since it will generate recording folder and settings json)
3. Run `MovementRec.exe`

## Usage

1. Launch `MovementRec.exe`
2. Select a target application window from the dropdown
3. Press **F3** (default) to start/stop recording
4. Press **F4** to pause/resume recording
5. Go to the **Playback** tab to assign recordings to slots with keybinds
6. Press the assigned key (e.g. **F2**) to trigger playback
7. Keybinds and profiles are configurable within the app

## Building from Source

### Prerequisites

- Python 3.10+
- Windows 10 or later
- [PyInstaller](https://pyinstaller.org/)

### Steps

```bash
# Clone the repository
git clone https://github.com/Infinite-Unknown/MovementRec.git
cd MovementRec

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# Build the exe
pyinstaller MovementRec.spec

# Output is in dist/MovementRec/
```

## Configuration

- `settings.json` is auto-created on first run in the same directory as the exe
- `recordings/` stores recorded input sequences as JSON files
- Both are portable and live alongside the executable

## Requirements

- Windows 10 or Windows 11
- Uses Win32 APIs: SendInput, Raw Input, low-level mouse/keyboard hooks
