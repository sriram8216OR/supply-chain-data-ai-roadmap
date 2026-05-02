"""
Histogram — bar histogram for distribution displays using PyQtGraph.

Used for the lag distribution on Tab 1.2: weeks-until-first-company-impact
weighted by company net exposure $.
"""

from __future__ import annotations

import numpy as np
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

from .. import theme
from .stacked_area_chart import _DollarAxis


class Histogram(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOption("background", theme.BG_RAISED)
        pg.setConfigOption("foreground", theme.TEXT_SECONDARY)
        pg.setConfigOption("antialias", True)

        self._plot = pg.PlotWidget()
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.setMenuEnabled(False)
        self._plot.hideButtons()
        self._plot.showGrid(x=False, y=True, alpha=0.15)
        self._plot.getAxis("left").setPen(QColor(theme.BORDER_SUBTLE))
        self._plot.getAxis("bottom").setPen(QColor(theme.BORDER_SUBTLE))
        self._plot.getAxis("left").setTextPen(QColor(theme.TEXT_SECONDARY))
        self._plot.getAxis("bottom").setTextPen(QColor(theme.TEXT_SECONDARY))
        self._plot.getAxis("left").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))
        self._plot.getAxis("bottom").setStyle(tickFont=QFont(theme.FONT_FAMILY_BASE, 9))
        self._plot.setAxisItems({"left": _DollarAxis(orientation="left")})

        self._plot.setLabel("bottom", "Week", color=theme.TEXT_SECONDARY)
        self._plot.setLabel("left", "Company net exposure ($)", color=theme.TEXT_SECONDARY)

        layout.addWidget(self._plot)
        self.setMinimumHeight(200)

        self._bars_item = None

    def set_bars(self, x: np.ndarray, heights: np.ndarray, color: str = theme.MODE_OCEAN):
        """Plot bars at integer x positions with corresponding heights."""
        self._plot.clear()
        if len(x) == 0:
            return
        bg = pg.BarGraphItem(
            x=x, height=heights, width=0.85,
            brush=QColor(color), pen=pg.mkPen(color=QColor(color), width=0),
        )
        self._plot.addItem(bg)
        max_y = float(heights.max()) if len(heights) else 0
        if max_y == 0:
            max_y = 1
        self._plot.setYRange(0, max_y * 1.10, padding=0)
        self._plot.setXRange(x.min() - 0.6, x.max() + 0.6, padding=0)
