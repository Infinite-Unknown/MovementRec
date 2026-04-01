"""Project Info tab — version, ASCII art, GitHub link, and update info."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

license = [" ∞ | MovementRec V1.0.0 (Release) ",
           "⠀⠀⠀ ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀ ⠀⠀⠀⣠⠾⡄⠀",
           "⠀⠀ ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⡆⠀⠀⠀ ⠀⠀⣠⡞⠁⠀⣧⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡠⠖⠋ ⣽⣀⣤⣤⣄⡴⠊⡹⢻⠀⠀⢸⠀⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⡤⣶⡶⠚⠉⠀⠀⠈⠁⢀⣩⢼⠟⠀⠀⢁⡼⠀⠀⢸⠀⠀⠀ ",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⠋⠰⠋⠀⠀⠀⠀⠀⣠⠔⠋⢠⠏⠀⠀⣠⣾⠁⠀⠀⡏⠀⣠⠀ ",
           "⠀⠀⠀⠀⠀⠀⠀⠀⢀⣸⡇⠀⠀⠀⠀⠀⣠⡴⠋⠀⠀⣠⠏⠀⠀⢠⡿⠋⠀⢀⣠⠗⠋⢈⡆ ",
           "⠀⠀⠀⠀⠀⠀⠀⣴⠋⠙⠳⡄⠀⠀⠀⠾⠉⠀⠀⢀⣴⣏⠀⠀⢠⠹⣇⣤⡾⠋⠠⣾⡇⢸⡇ ",
           "⠀⠀⠀⠀⠀⠀⣀⣴⣿⣦⡀⠀⠙⢦⡀⠀⠀⠀⢀⣠⡼⠟⠁⠀⣀⡼⠋⣡⠋⠀⠀⣠⡏⠀⡜⠀",
           "⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣄⠀⠀⠳⡄⠀⠀⠀⢀⣀⣠⡶⠿⡇⣤⡾⠁⠀⠀⡾⠟⠀⣰⠃⠀",
           "⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣧⡀⣀⣹⣦⣶⣊⠉⠀⢀⠄⢠⠿⠋⠀⠀⢠⣼⠛⠀⡴⠃⠀⠀",
           "⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡄⠀⢀⠏⠀⢀⡤⠖⠋⠀⣠⠞⠁⠀⠀⠀",
           "⠘⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣤⠏⠀⠀⠀⠀⢀⣠⢾⠇⠀⠀⠀⠀⠀",
           "⠀⠈⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠁⠶⣶⣤⣤⠼⠟⠁⣸⡇⠀⠀⠀⠀⠀",
           "⠀⠀⠀⠀⠉⠛⠿⠿⠿⠛⠛⠛⠛⠻⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀⠀⠀⠀⣰⡟⠁⠀⠀⠀⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣇⡈⠉⠁⠀⢀⡀⠀⠀⠀⠀⠀⠀⠈⠻⠿⣯⠀⠀⠀⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡤⠞⠋⠁⠀⠀⠀⠸⡌⠙⠢⣄⠀⠀⠀⣠⠴⢊⣿⡇⠀⠀⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠱⢤⡀⠀⠀⠀⠀⠀⠙⢦⡀⠘⣄⣤⣾⣿⣴⣿⠋⠀⠀⠀⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠻⣝⡒⠂⠀⠀⠀⠀⢱⣾⠟⠉⡟⠁⠸⠾⠀⠀⠀⠀⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⣿⠀⠀⠀⠀⣿⠪⣷⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
           "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠁⠈⠙⠒⠊⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀"]


class ProjectInfoTab(QWidget):
    """Project info tab with ASCII art, GitHub link, and update info."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        layout.addStretch()

        # ASCII art
        art_text = "\n".join(license)
        art_label = QLabel(art_text)
        art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        art_font = QFont("Consolas", 9)
        art_font.setStyleHint(QFont.StyleHint.Monospace)
        art_label.setFont(art_font)
        art_label.setStyleSheet("color: #00B4D8; background: transparent;")
        layout.addWidget(art_label)

        layout.addSpacing(10)

        # GitHub link
        gh_row = QHBoxLayout()
        gh_row.setSpacing(8)
        gh_row.addStretch()

        gh_icon = QLabel("GitHub:")
        gh_icon.setStyleSheet("color: #AAA; font-size: 13px; font-weight: bold;")
        gh_row.addWidget(gh_icon)

        gh_btn = QPushButton("https://github.com/Infinite-Unknown/MovementRec")
        gh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gh_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #58A6FF;
                border: none; font-size: 13px; text-decoration: underline;
                padding: 4px 0;
            }
            QPushButton:hover { color: #79C0FF; }
        """)
        gh_btn.setToolTip("Open in browser")
        gh_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/Infinite-Unknown/MovementRec")
            )
        )
        gh_row.addWidget(gh_btn)
        gh_row.addStretch()

        layout.addLayout(gh_row)

        layout.addSpacing(10)

        # Auto update coming soon
        update_label = QLabel("Auto Update Manager — Coming Soon")
        update_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        update_label.setStyleSheet(
            "color: #888; font-size: 12px; font-style: italic; padding: 8px;"
        )
        layout.addWidget(update_label)

        layout.addStretch()
