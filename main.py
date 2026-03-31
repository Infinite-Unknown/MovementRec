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
    base_dir = Path(__file__).parent.resolve()
    settings_path = base_dir / "settings.json"
    settings = Settings.load(settings_path)

    app = QApplication(sys.argv)
    app.setApplicationName("MovementRec")
    app.setOrganizationName("MovementRec")

    icon_path = base_dir / "icon.ico"
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
