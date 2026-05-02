"""
FingerprintMetric — small label + value vertical pair, used in the vulnerability
fingerprint footer row on Tab 1.1.

Several of these stack horizontally to form the network's "fingerprint" — a row
of compact metrics characterizing structural fragility.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from .. import theme


class FingerprintMetric(QFrame):
    """A compact label + value pair."""

    def __init__(self, label: str, value: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_MD, theme.SPACING_SM,
            theme.SPACING_MD, theme.SPACING_SM,
        )
        layout.setSpacing(theme.SPACING_XS)

        self._label = QLabel(label.upper())
        self._label.setObjectName("fp_label")
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self._value = QLabel(value)
        self._value.setObjectName("fp_value")
        self._value.setWordWrap(True)
        layout.addWidget(self._value)

    def set_value(self, value: str):
        self._value.setText(value)
