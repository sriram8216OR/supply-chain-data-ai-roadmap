"""
DonutChart — custom QPainter-rendered donut chart for compact data display.

Used for the mode-mix donut on Tab 1.1. Custom painted because the visual
density we want (small chart + center text + outside labels) is awkward to
get right with general-purpose chart libraries.

Slice data is a list of (label, value, color) tuples.
"""

from __future__ import annotations

from typing import List, Tuple

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PyQt5.QtWidgets import QWidget

from .. import theme


SliceData = Tuple[str, float, str]  # (label, value, hex_color)


class DonutChart(QWidget):
    """Donut chart with optional center text and outside slice labels."""

    def __init__(
        self,
        slices: List[SliceData] | None = None,
        center_top: str = "",
        center_bottom: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._slices: List[SliceData] = slices or []
        self._center_top = center_top
        self._center_bottom = center_bottom
        self.setMinimumSize(280, 240)

    def set_data(
        self,
        slices: List[SliceData],
        center_top: str = "",
        center_bottom: str = "",
    ):
        self._slices = slices
        self._center_top = center_top
        self._center_bottom = center_bottom
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self._slices:
            self._paint_empty(painter)
            return

        total = sum(v for _, v, _ in self._slices)
        if total <= 0:
            self._paint_empty(painter)
            return

        rect = self.rect()
        # Reserve space for outside labels (left, right, top, bottom of donut)
        label_padding_x = 60
        label_padding_y = 24
        size = min(rect.width() - 2 * label_padding_x,
                   rect.height() - 2 * label_padding_y)
        if size <= 60:
            size = max(60, min(rect.width() - 20, rect.height() - 30))

        cx = rect.center().x()
        cy = rect.center().y()
        radius_outer = size / 2
        radius_inner = radius_outer * 0.62  # donut hole

        donut_rect = QRectF(cx - radius_outer, cy - radius_outer,
                            size, size)

        # Paint slices
        start_angle_deg = 90.0  # 12 o'clock start
        painter.setPen(QPen(QColor(theme.BG_BASE), 2))
        for (_label, value, color_hex) in self._slices:
            span_deg = -(value / total) * 360.0  # negative = clockwise
            painter.setBrush(QBrush(QColor(color_hex)))
            # QPainter angles are 1/16th degree
            painter.drawPie(
                donut_rect,
                int(start_angle_deg * 16),
                int(span_deg * 16),
            )
            start_angle_deg += span_deg

        # Punch out center hole (donut)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(theme.BG_BASE)))
        inner_rect = QRectF(
            cx - radius_inner, cy - radius_inner,
            radius_inner * 2, radius_inner * 2,
        )
        painter.drawEllipse(inner_rect)

        # Center text
        if self._center_top:
            painter.setPen(QColor(theme.TEXT_PRIMARY))
            font = QFont(painter.font())
            font.setPointSize(theme.FONT_SIZE_HEADING)
            font.setWeight(QFont.DemiBold)
            painter.setFont(font)
            top_rect = QRectF(cx - radius_inner, cy - 14,
                              radius_inner * 2, 22)
            painter.drawText(top_rect, Qt.AlignHCenter | Qt.AlignVCenter,
                             self._center_top)

        if self._center_bottom:
            painter.setPen(QColor(theme.TEXT_MUTED))
            font = QFont(painter.font())
            font.setPointSize(theme.FONT_SIZE_TINY)
            font.setWeight(QFont.Normal)
            painter.setFont(font)
            bot_rect = QRectF(cx - radius_inner, cy + 8,
                              radius_inner * 2, 18)
            painter.drawText(bot_rect, Qt.AlignHCenter | Qt.AlignVCenter,
                             self._center_bottom)

        # Slice labels (drawn outside slices, anchored to the slice midpoint angle)
        from math import sin, cos, radians
        start_angle_deg = 90.0
        font = QFont(painter.font())
        font.setPointSize(theme.FONT_SIZE_SMALL)
        font.setWeight(QFont.Medium)
        painter.setFont(font)

        for (label, value, color_hex) in self._slices:
            span_deg = -(value / total) * 360.0
            mid_deg = start_angle_deg + span_deg / 2
            # Convert to standard math angle (Qt: 0=3 o'clock, CCW positive; same here)
            rad = radians(mid_deg)
            label_radius = radius_outer + 18
            lx = cx + label_radius * cos(rad)
            ly = cy - label_radius * sin(rad)  # Qt y is down

            pct = value / total * 100
            label_text = f"{label.title()}  {pct:.0f}%"

            painter.setPen(QColor(theme.TEXT_SECONDARY))
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(label_text)
            text_h = metrics.height()
            # Anchor: if on right half, left-align; on left half, right-align
            if cos(rad) > 0:
                text_x = lx
            else:
                text_x = lx - text_w
            text_y = ly - text_h / 2
            painter.drawText(
                QRectF(text_x, text_y, text_w, text_h),
                Qt.AlignLeft | Qt.AlignVCenter,
                label_text,
            )

            start_angle_deg += span_deg

    def _paint_empty(self, painter: QPainter):
        painter.setPen(QColor(theme.TEXT_MUTED))
        painter.drawText(self.rect(), Qt.AlignCenter, "No data")
