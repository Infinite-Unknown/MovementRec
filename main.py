"""MovementRec - Input/Movement Recorder

Entry point for the application.
"""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.models import Settings
from ui.main_window import MainWindow


def main():
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent.resolve()
        bundle_dir = Path(getattr(sys, '_MEIPASS', base_dir)).resolve()
    else:
        base_dir = Path(__file__).parent.resolve()
        bundle_dir = base_dir
    settings_path = base_dir / "settings.json"
    settings = Settings.load(settings_path)

    app = QApplication(sys.argv)
    app.setApplicationName("MovementRec")
    app.setOrganizationName("MovementRec")

    icon_path = bundle_dir / "icon.ico"
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    window = MainWindow(settings, base_dir)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
