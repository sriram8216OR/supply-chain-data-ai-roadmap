"""
StackedBar — custom horizontal stacked bar with inline labels.

Used for contract archetype concentration on Tab 1.1: a single horizontal bar
where each segment represents a category share, with the segment's own label
written inside the segment if there's room.
"""

from __future__ import annotations

from typing import List, Tuple

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt5.QtWidgets import QWidget

from .. import theme


SegmentData = Tuple[str, float, str]  # (label, value, hex_color)


class StackedBar(QWidget):
    """Horizontal stacked bar with inline labels."""

    def __init__(self, segments: List[SegmentData] | None = None, parent=None):
        super().__init__(parent)
        self._segments: List[SegmentData] = segments or []
        self.setMinimumHeight(56)
        self.setMaximumHeight(56)

    def set_segments(self, segments: List[SegmentData]):
        self._segments = segments
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        if not self._segments:
            painter.setPen(QColor(theme.TEXT_MUTED))
            painter.drawText(rect, Qt.AlignCenter, "No data")
            return

        total = sum(v for _, v, _ in self._segments)
        if total <= 0:
            return

        # Bar geometry
        bar_height = 36
        bar_y = (rect.height() - bar_height) / 2
        bar_left = 4
        bar_right = rect.width() - 4
        bar_width = bar_right - bar_left

        font = QFont(painter.font())
        font.setPointSize(theme.FONT_SIZE_SMALL)
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        x = bar_left
        painter.setPen(Qt.NoPen)
        for (label, value, color_hex) in self._segments:
            seg_w = bar_width * (value / total)
            painter.setBrush(QBrush(QColor(color_hex)))
            painter.drawRect(QRectF(x, bar_y, seg_w, bar_height))

            pct = value / total * 100
            seg_label = f"{label}  {pct:.0f}%"
            label_w = metrics.horizontalAdvance(seg_label)
            if label_w + 8 < seg_w:
                # Fits inline
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(
                    QRectF(x, bar_y, seg_w, bar_height),
                    Qt.AlignCenter,
                    seg_label,
                )
                painter.setPen(Qt.NoPen)
            elif seg_w > 30:
                # Just a percent
                short = f"{pct:.0f}%"
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(
                    QRectF(x, bar_y, seg_w, bar_height),
                    Qt.AlignCenter,
                    short,
                )
                painter.setPen(Qt.NoPen)
            x += seg_w
