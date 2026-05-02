"""
StackedAreaChart — time-phased stacked area chart using PyQtGraph.

Used for the time-phased company net exposure curves on Tab 1.2:
  - X axis: weeks from shock event
  - Y axis: cumulative company net exposure ($)
  - Stacked layers: by mode (air, ocean, truck)
  - Vertical reference lines: first company impact, steady state

Designed to redraw efficiently when the shock value changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QPen
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

from .. import theme


@dataclass
class AreaSeries:
    label: str
    values: np.ndarray  # length = len(weeks)
    color: str          # hex


class StackedAreaChart(QWidget):
    """Stacked area chart with optional vertical reference lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Configure pyqtgraph defaults to match our theme
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

        # Y axis tick formatter (dollars)
        self._plot.getAxis("left").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))
        self._plot.getAxis("bottom").setStyle(tickFont=QFont(theme.FONT_FAMILY_BASE, 9))

        # Use a custom AxisItem for left to format y-tick values
        self._plot.setAxisItems({"left": _DollarAxis(orientation="left")})

        self._plot.setLabel("bottom", "Weeks from shock event",
                            color=theme.TEXT_SECONDARY)
        self._plot.setLabel("left", "Cumulative company net exposure ($)",
                            color=theme.TEXT_SECONDARY)

        layout.addWidget(self._plot)

        self.setMinimumHeight(260)

        # Track ref-line items so we can clear them between updates
        self._reflines: list = []

    def set_data(
        self,
        weeks: np.ndarray,
        series_list: List[AreaSeries],
        first_impact_week: int = 0,
        steady_state_week: int = 0,
    ):
        """Render the stacked area chart.

        weeks: 1D array of week indices, e.g. arange(0, 27)
        series_list: list of AreaSeries; each .values must have same length as weeks
        first_impact_week / steady_state_week: optional vertical reference lines
        """
        self._plot.clear()
        for ref in self._reflines:
            self._plot.removeItem(ref)
        self._reflines.clear()

        if len(series_list) == 0:
            self._plot.setYRange(0, 1)
            self._plot.setXRange(0, max(1, weeks.max()))
            return

        # Stack the series progressively
        baseline = np.zeros(len(weeks))
        for series in series_list:
            top = baseline + series.values
            color = QColor(series.color)
            color.setAlpha(220)
            curve_top = pg.PlotCurveItem(weeks, top, pen=pg.mkPen(color=color, width=1))
            curve_bot = pg.PlotCurveItem(weeks, baseline, pen=pg.mkPen(color=color, width=0))
            fill = pg.FillBetweenItem(curve_top, curve_bot, brush=color)
            self._plot.addItem(fill)
            self._plot.addItem(curve_top)
            baseline = top

        # Set ranges
        max_y = float(baseline.max()) if len(baseline) else 0
        if max_y == 0:
            max_y = 1
        self._plot.setYRange(0, max_y * 1.10, padding=0)
        self._plot.setXRange(weeks.min(), weeks.max(), padding=0.02)

        # Reference lines
        if first_impact_week > 0:
            line = pg.InfiniteLine(
                pos=first_impact_week, angle=90,
                pen=pg.mkPen(color=theme.TEXT_MUTED, width=1, style=Qt.DotLine),
                label=f"first company impact (wk {first_impact_week})",
                labelOpts={
                    "position": 0.92,
                    "color": theme.TEXT_MUTED,
                    "fill": theme.BG_RAISED,
                    "movable": False,
                },
            )
            self._plot.addItem(line)
            self._reflines.append(line)

        if 0 < steady_state_week and steady_state_week != first_impact_week:
            line = pg.InfiniteLine(
                pos=steady_state_week, angle=90,
                pen=pg.mkPen(color=theme.TEXT_MUTED, width=1, style=Qt.DotLine),
                label=f"steady state (wk {steady_state_week})",
                labelOpts={
                    "position": 0.92,
                    "color": theme.TEXT_MUTED,
                    "fill": theme.BG_RAISED,
                    "movable": False,
                },
            )
            self._plot.addItem(line)
            self._reflines.append(line)


class _DollarAxis(pg.AxisItem):
    """Custom y-axis that formats tick values as $X.XM."""

    def tickStrings(self, values, scale, spacing):
        out = []
        for v in values:
            if abs(v) >= 1e9:
                out.append(f"${v / 1e9:.1f}B")
            elif abs(v) >= 1e6:
                out.append(f"${v / 1e6:.1f}M")
            elif abs(v) >= 1e3:
                out.append(f"${v / 1e3:.0f}K")
            else:
                out.append(f"${v:.0f}")
        return out
