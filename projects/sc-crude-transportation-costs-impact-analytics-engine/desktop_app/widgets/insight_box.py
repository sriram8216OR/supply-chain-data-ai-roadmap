"""
InsightBox widget — a left-accent-bar panel for auto-generated headline insights.

Renders the "💡 Headline insight: ..." sentence at the bottom of each tab.
Supports rich text (HTML) for bolding key numbers/terms.
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout

from .. import theme


class InsightBox(QFrame):
    """Headline-insight callout with left blue accent bar."""

    def __init__(self, html: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("insight_box")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )
        layout.setSpacing(theme.SPACING_XS)

        self._label = QLabel("HEADLINE INSIGHT")
        self._label.setObjectName("insight_label")
        layout.addWidget(self._label)

        self._text = QLabel(html)
        self._text.setObjectName("insight_text")
        self._text.setWordWrap(True)
        self._text.setTextFormat(Qt.RichText)
        self._text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._text)

    def set_html(self, html: str):
        self._text.setText(html)
