"""
TimePhasedDualChart — vertically-stacked cumulative + incremental view.

  Top panel:    cumulative stacked area (same as Tab 1.2 chart, but sliced by
                a configurable dimension — mode, lane_type, archetype, etc.)
  Bottom panel: weekly increment bars showing the per-week delta — the *pulse*
                that hits each week, not the running total.

Both panels share the same x-axis (weeks 0 to horizon). Reference lines
optional on either panel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QVBoxLayout, QWidget
import pyqtgraph as pg

from .. import theme
from .stacked_area_chart import _DollarAxis


@dataclass
class StackSeries:
    """One series in the stack. values is length-N for cumulative chart."""
    label: str
    values: np.ndarray  # cumulative values per week (same length as weeks)
    color: str          # hex


class TimePhasedDualChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        pg.setConfigOption("background", theme.BG_RAISED)
        pg.setConfigOption("foreground", theme.TEXT_SECONDARY)
        pg.setConfigOption("antialias", True)

        # Top: cumulative
        self._top = pg.PlotWidget()
        self._top.setMouseEnabled(x=False, y=False)
        self._top.setMenuEnabled(False)
        self._top.hideButtons()
        self._top.showGrid(x=False, y=True, alpha=0.12)
        self._top.getAxis("left").setPen(QColor(theme.BORDER_SUBTLE))
        self._top.getAxis("bottom").setPen(QColor(theme.BORDER_SUBTLE))
        self._top.getAxis("left").setTextPen(QColor(theme.TEXT_SECONDARY))
        self._top.getAxis("bottom").setTextPen(QColor(theme.TEXT_SECONDARY))
        self._top.getAxis("left").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))
        self._top.getAxis("bottom").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))
        self._top.setAxisItems({"left": _DollarAxis(orientation="left")})
        self._top.setLabel("left", "Cumulative ($)", color=theme.TEXT_SECONDARY)
        # Hide bottom axis labels on top chart (shared with bottom chart)
        self._top.getAxis("bottom").setStyle(showValues=False)
        layout.addWidget(self._top, 3)

        # Bottom: increments
        self._bot = pg.PlotWidget()
        self._bot.setMouseEnabled(x=False, y=False)
        self._bot.setMenuEnabled(False)
        self._bot.hideButtons()
        self._bot.showGrid(x=False, y=True, alpha=0.12)
        self._bot.getAxis("left").setPen(QColor(theme.BORDER_SUBTLE))
        self._bot.getAxis("bottom").setPen(QColor(theme.BORDER_SUBTLE))
        self._bot.getAxis("left").setTextPen(QColor(theme.TEXT_SECONDARY))
        self._bot.getAxis("bottom").setTextPen(QColor(theme.TEXT_SECONDARY))
        self._bot.getAxis("left").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))
        self._bot.getAxis("bottom").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))
        self._bot.setAxisItems({"left": _DollarAxis(orientation="left")})
        self._bot.setLabel("left", "Weekly increment ($)", color=theme.TEXT_SECONDARY)
        self._bot.setLabel("bottom", "Weeks from shock event", color=theme.TEXT_SECONDARY)
        layout.addWidget(self._bot, 2)

        # Link x-axis ranges so they always match
        self._bot.setXLink(self._top)

        self.setMinimumHeight(420)

        self._reflines: list = []

    def set_data(
        self,
        weeks: np.ndarray,
        series_list: list[StackSeries],
        first_impact_week: int = 0,
        steady_state_week: int = 0,
    ):
        """Render both charts.

        weeks: 1D array, e.g. arange(0, horizon+1)
        series_list: list of StackSeries with cumulative values per week
        """
        self._top.clear()
        self._bot.clear()
        for ref in self._reflines:
            try:
                self._top.removeItem(ref)
                self._bot.removeItem(ref)
            except Exception:
                pass
        self._reflines.clear()

        if not series_list or len(weeks) == 0:
            self._top.setYRange(0, 1)
            self._bot.setYRange(0, 1)
            return

        # ---- Top: cumulative stacked area ----
        baseline = np.zeros(len(weeks))
        for series in series_list:
            top = baseline + series.values
            color = QColor(series.color)
            color.setAlpha(220)
            curve_top = pg.PlotCurveItem(weeks, top, pen=pg.mkPen(color, width=1))
            curve_bot = pg.PlotCurveItem(weeks, baseline, pen=pg.mkPen(color, width=0))
            fill = pg.FillBetweenItem(curve_top, curve_bot, brush=color)
            self._top.addItem(fill)
            self._top.addItem(curve_top)
            baseline = top

        max_cum = float(baseline.max()) if len(baseline) else 0
        if max_cum == 0:
            max_cum = 1
        self._top.setYRange(0, max_cum * 1.10, padding=0)
        self._top.setXRange(weeks.min(), weeks.max(), padding=0.02)

        # ---- Bottom: weekly increments (stacked bars) ----
        # Compute per-series incremental (delta) per week
        n = len(weeks)
        bar_width = 0.8
        bottoms = np.zeros(n)
        for series in series_list:
            cum = series.values
            inc = np.zeros(n)
            inc[0] = cum[0]
            for i in range(1, n):
                inc[i] = cum[i] - cum[i - 1]
            color = QColor(series.color)
            color.setAlpha(230)
            bg = pg.BarGraphItem(
                x=weeks, height=inc, width=bar_width, y0=bottoms,
                brush=color, pen=pg.mkPen(color, width=0),
            )
            self._bot.addItem(bg)
            bottoms = bottoms + inc

        max_inc = float(bottoms.max()) if len(bottoms) else 0
        if max_inc == 0:
            max_inc = 1
        self._bot.setYRange(0, max_inc * 1.15, padding=0)

        # ---- Reference lines on top chart ----
        if first_impact_week > 0:
            line = pg.InfiniteLine(
                pos=first_impact_week, angle=90,
                pen=pg.mkPen(color=theme.TEXT_MUTED, width=1, style=Qt.DotLine),
                label=f"first impact (wk {first_impact_week})",
                labelOpts={
                    "position": 0.92,
                    "color": theme.TEXT_MUTED,
                    "fill": theme.BG_RAISED,
                    "movable": False,
                },
            )
            self._top.addItem(line)
            self._reflines.append(line)

        if steady_state_week > 0 and steady_state_week != first_impact_week:
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
            self._top.addItem(line)
            self._reflines.append(line)
