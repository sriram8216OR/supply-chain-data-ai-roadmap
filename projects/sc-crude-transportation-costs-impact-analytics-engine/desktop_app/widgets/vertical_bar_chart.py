"""
VerticalBarChart — custom QPainter bar chart with multi-line labels above bars.

Used for the lane_type breakdown on Tab 1.1. Each bar has:
  - A bar height proportional to its value
  - Above the bar: a value label (formatted dollar amount), a share label, lane count
  - Below the bar: the category name
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush
from PyQt5.QtWidgets import QWidget

from .. import theme


@dataclass
class Bar:
    label: str           # under-bar label (e.g., "Inbound Component")
    value: float         # bar height value
    color: str           # hex color
    primary_text: str    # bold text above bar (e.g., "$36M")
    secondary_text: str  # below primary, smaller (e.g., "38% of network")
    tertiary_text: str = ""  # optional third line (e.g., "22 lanes")


class VerticalBarChart(QWidget):
    """Vertical bar chart with multi-line labels."""

    def __init__(self, bars: List[Bar] | None = None, parent=None):
        super().__init__(parent)
        self._bars: List[Bar] = bars or []
        self.setMinimumHeight(220)

    def set_bars(self, bars: List[Bar]):
        self._bars = bars
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        if not self._bars:
            painter.setPen(QColor(theme.TEXT_MUTED))
            painter.drawText(rect, Qt.AlignCenter, "No data")
            return

        max_value = max(b.value for b in self._bars)
        if max_value <= 0:
            return

        # Layout: top space for 3-line labels, bar area, bottom for category labels
        top_label_height = 60
        bottom_label_height = 24
        side_padding = 16

        chart_top = rect.top() + top_label_height
        chart_bottom = rect.bottom() - bottom_label_height
        chart_height = chart_bottom - chart_top
        chart_left = rect.left() + side_padding
        chart_right = rect.right() - side_padding
        chart_width = chart_right - chart_left

        n_bars = len(self._bars)
        # Each bar gets equal slot; bar itself takes ~60% of slot width
        slot_width = chart_width / n_bars
        bar_width = slot_width * 0.62

        # Faint baseline
        painter.setPen(QPen(QColor(theme.BORDER_SUBTLE), 1))
        painter.drawLine(chart_left, chart_bottom, chart_right, chart_bottom)

        for i, bar in enumerate(self._bars):
            slot_center = chart_left + slot_width * (i + 0.5)
            bar_left = slot_center - bar_width / 2
            bar_height = chart_height * (bar.value / max_value)
            # Minimum visible height — guarantees tiny bars stay visible
            min_bar_h = chart_height * 0.04
            if bar_height < min_bar_h:
                bar_height = min_bar_h
            bar_top = chart_bottom - bar_height

            # Bar
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(bar.color)))
            painter.drawRect(QRectF(bar_left, bar_top, bar_width, bar_height))

            # Multi-line labels above bar
            label_x = slot_center - slot_width / 2
            label_w = slot_width
            label_y_start = bar_top - top_label_height + 6

            # Primary (bold, brighter)
            font = QFont(painter.font())
            font.setPointSize(theme.FONT_SIZE_LARGE)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            painter.setPen(QColor(theme.TEXT_PRIMARY))
            painter.drawText(
                QRectF(label_x, label_y_start, label_w, 18),
                Qt.AlignHCenter | Qt.AlignVCenter,
                bar.primary_text,
            )

            # Secondary (regular, muted)
            font.setPointSize(theme.FONT_SIZE_TINY)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor(theme.TEXT_SECONDARY))
            painter.drawText(
                QRectF(label_x, label_y_start + 18, label_w, 14),
                Qt.AlignHCenter | Qt.AlignVCenter,
                bar.secondary_text,
            )

            # Tertiary (smallest, muted)
            if bar.tertiary_text:
                painter.setPen(QColor(theme.TEXT_MUTED))
                painter.drawText(
                    QRectF(label_x, label_y_start + 32, label_w, 14),
                    Qt.AlignHCenter | Qt.AlignVCenter,
                    bar.tertiary_text,
                )

            # Category label below bar
            font.setPointSize(theme.FONT_SIZE_SMALL)
            font.setWeight(QFont.Medium)
            painter.setFont(font)
            painter.setPen(QColor(theme.TEXT_SECONDARY))
            painter.drawText(
                QRectF(label_x, chart_bottom + 6, label_w, bottom_label_height - 6),
                Qt.AlignHCenter | Qt.AlignTop,
                bar.label,
            )
