"""
HeadlineNumber widget — a panel with a small uppercase label, a big monospace
value, and optional subtext below.

Used for the headline metrics rows on Page 1 and other dashboards.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from .. import theme


class HeadlineNumber(QFrame):
    """Panel with label, large value, and optional subtext."""

    def __init__(
        self,
        label: str,
        value: str = "—",
        subtext: str = "",
        size: str = "default",   # "default" | "large"
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_MD, theme.SPACING_SM,
            theme.SPACING_MD, theme.SPACING_SM,
        )
        layout.setSpacing(theme.SPACING_XS)

        self._label = QLabel(label.upper())
        self._label.setObjectName("headline_label")
        layout.addWidget(self._label)

        self._value = QLabel(value)
        if size == "large":
            self._value.setObjectName("headline_value_large")
        else:
            self._value.setObjectName("headline_value")
        self._value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._value)

        self._subtext = QLabel(subtext)
        self._subtext.setObjectName("headline_subtext")
        self._subtext.setVisible(bool(subtext))
        self._subtext.setWordWrap(True)
        layout.addWidget(self._subtext)

    def set_value(self, value: str):
        self._value.setText(value)

    def set_subtext(self, subtext: str):
        self._subtext.setText(subtext)
        self._subtext.setVisible(bool(subtext))

    def set_label(self, label: str):
        self._label.setText(label.upper())
