"""
ParetoCurve — cumulative concentration line plot using pyqtgraph.

Used on Page 3 to show how exposure is distributed across ranked lanes.

  X axis: rank (1 = top lane, increasing to total lane count)
  Y axis: cumulative % of total metric (0 to 100)

Optional features:
  - Horizontal reference lines at 50% and 80%
  - Annotated markers at specific rank positions (e.g., rank 5, 10, 25)
"""

from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QVBoxLayout, QWidget
import pyqtgraph as pg

from .. import theme


class ParetoCurve(QWidget):
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
        self._plot.showGrid(x=True, y=True, alpha=0.12)

        for axis_name in ("left", "bottom"):
            ax = self._plot.getAxis(axis_name)
            ax.setPen(QColor(theme.BORDER_SUBTLE))
            ax.setTextPen(QColor(theme.TEXT_SECONDARY))

        self._plot.getAxis("left").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))
        self._plot.getAxis("bottom").setStyle(tickFont=QFont(theme.FONT_FAMILY_MONO, 9))

        self._plot.setLabel("bottom", "Lane rank (sorted by metric, descending)",
                            color=theme.TEXT_SECONDARY)
        self._plot.setLabel("left", "Cumulative % of total exposure",
                            color=theme.TEXT_SECONDARY)

        layout.addWidget(self._plot)
        self.setMinimumHeight(320)

        # Track items for clearing
        self._items: list = []

    def set_data(
        self,
        ranks: np.ndarray,
        cumulative_pct: np.ndarray,
        marker_ranks: list[int] | None = None,
    ):
        """Render the Pareto curve.

        ranks: 1D array, e.g. [1, 2, 3, ..., n]
        cumulative_pct: same length, values 0..100
        marker_ranks: optional list of ranks (e.g. [5, 10, 25]) where to draw labeled markers
        """
        self._plot.clear()
        for it in self._items:
            self._plot.removeItem(it)
        self._items.clear()

        if len(ranks) == 0:
            return

        # Curve
        curve_color = QColor(theme.ACCENT_PRIMARY)
        curve = pg.PlotDataItem(
            ranks, cumulative_pct,
            pen=pg.mkPen(curve_color, width=2.2),
            symbol=None,
        )
        self._plot.addItem(curve)
        self._items.append(curve)

        # Fill under curve
        baseline = pg.PlotCurveItem(ranks, np.zeros_like(cumulative_pct),
                                     pen=pg.mkPen(curve_color, width=0))
        top_curve = pg.PlotCurveItem(ranks, cumulative_pct,
                                      pen=pg.mkPen(curve_color, width=0))
        fill_color = QColor(curve_color)
        fill_color.setAlpha(40)
        fill = pg.FillBetweenItem(top_curve, baseline, brush=fill_color)
        self._plot.addItem(fill)
        self._plot.addItem(top_curve)
        self._items.extend([fill, top_curve])

        # Reference lines at 50% and 80%
        for ref_pct, ref_label in [(50, "50%"), (80, "80%")]:
            ref_line = pg.InfiniteLine(
                pos=ref_pct, angle=0,
                pen=pg.mkPen(color=theme.TEXT_MUTED, width=1, style=Qt.DotLine),
                label=ref_label,
                labelOpts={
                    "position": 0.02,
                    "color": theme.TEXT_MUTED,
                    "fill": theme.BG_RAISED,
                    "movable": False,
                },
            )
            self._plot.addItem(ref_line)
            self._items.append(ref_line)

        # Annotated markers at specific ranks
        if marker_ranks:
            n = len(ranks)
            for r in marker_ranks:
                if r < 1 or r > n:
                    continue
                # Get the cumulative % at that rank
                idx = r - 1
                pct = float(cumulative_pct[idx])

                # Marker dot
                marker = pg.ScatterPlotItem(
                    [r], [pct], size=8,
                    brush=QColor(theme.SEV_HIGH),
                    pen=pg.mkPen(QColor(theme.TEXT_PRIMARY), width=1.4),
                )
                self._plot.addItem(marker)
                self._items.append(marker)

                # Annotation text
                ann = pg.TextItem(
                    text=f"Top {r} = {pct:.0f}%",
                    color=theme.TEXT_PRIMARY,
                    anchor=(0, 1.3),  # bottom-left of point so it appears above
                )
                ann.setPos(r, pct)
                font = QFont(theme.FONT_FAMILY_MONO, theme.FONT_SIZE_TINY)
                font.setWeight(QFont.DemiBold)
                ann.setFont(font)
                self._plot.addItem(ann)
                self._items.append(ann)

        self._plot.setXRange(0, ranks.max() + 1, padding=0.02)
        self._plot.setYRange(0, 105, padding=0)
