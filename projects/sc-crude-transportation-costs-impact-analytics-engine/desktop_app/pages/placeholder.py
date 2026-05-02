"""Placeholder page widget for pages not yet built."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

from .. import theme


class PlaceholderPage(QWidget):
    def __init__(self, page_name: str, status: str = "Coming soon"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(f"{page_name}\n\n{status}")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: {theme.FONT_SIZE_LARGE}px;"
        )
        layout.addWidget(label)
