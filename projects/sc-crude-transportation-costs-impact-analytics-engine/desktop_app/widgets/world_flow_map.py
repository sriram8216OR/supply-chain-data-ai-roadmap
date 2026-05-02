"""
WorldFlowMap — custom QPainter widget rendering a world map with flow arcs.

Projection: equirectangular (longitude → x, latitude → y, linearly).
Centered on longitude 0 (Atlantic-centered). Antimeridian-crossing arcs are
split into two segments so they exit one edge and re-enter the other.

Design:
  - Coastlines drawn as faint background polygons
  - Region anchors as small filled circles with radius proportional to
    total cost flowing through that region
  - Flow lanes as curved arcs from origin anchor to destination anchor:
      thickness = annual transportation cost
      color    = severity gradient (green → yellow → red) over the active metric
      opacity  = full when matches filters, ~30% when filtered out
  - Optional disruption hotspot markers (Hormuz, Suez, Panama)
  - Hover tooltip showing lane details

Key API:
  set_data(diagnostic, shock_result, options)  — set everything in one call
  set_options(options)                          — change filter/layer state only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import atan2, cos, sin, sqrt
from typing import List, Optional, Tuple

import pandas as pd
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF,
)
from PyQt5.QtWidgets import QToolTip, QWidget

from .. import theme
from .world_coastlines import WORLD_POLYGONS


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Map bounds — longitude is centered on 0, latitude clipped to ±75 (avoid Antarctica)
LNG_MIN, LNG_MAX = -180.0, 180.0
LAT_MIN, LAT_MAX = -55.0, 80.0

# Horizontal padding inside the widget where the map is drawn
PADDING_LR = 14
PADDING_TB = 14

# Coastline visual properties
COASTLINE_FILL = QColor(38, 42, 51)        # subtle dark fill
COASTLINE_STROKE = QColor(60, 65, 75)      # slightly lighter outline

# Anchor marker visual properties
ANCHOR_BORDER = QColor(theme.TEXT_PRIMARY)
ANCHOR_BORDER_WIDTH = 1.5
ANCHOR_MIN_RADIUS = 4
ANCHOR_MAX_RADIUS = 14

# Flow line visual properties
FLOW_MIN_WIDTH = 1.0
FLOW_MAX_WIDTH = 6.0
FLOW_DIM_OPACITY = 0.20

# Hotspot markers (lng, lat, color, label)
HOTSPOTS = [
    (56.3, 26.6, QColor(theme.SEV_HIGH), "Hormuz"),
    (32.5, 30.5, QColor(theme.SEV_MED), "Suez"),
    (-79.7, 9.1, QColor(theme.SEV_MED), "Panama"),
]


# ---------------------------------------------------------------------------
# Severity gradient utility
# ---------------------------------------------------------------------------

def severity_color(t: float) -> QColor:
    """Map t in [0, 1] to severity gradient:
        0.0 → green (insulated)
        0.5 → yellow
        1.0 → red (high exposure)
    Uses sequential green → yellow → red interpolation in HSV-like space.
    """
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        # green → yellow
        u = t * 2  # 0..1
        r = int(74 + (242 - 74) * u)
        g = int(139 + (193 - 139) * u)
        b = int(111 + (78 - 111) * u)
    else:
        # yellow → red
        u = (t - 0.5) * 2
        r = int(242 + (233 - 242) * u)
        g = int(193 + (75 - 193) * u)
        b = int(78 + (92 - 78) * u)
    return QColor(r, g, b)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MapOptions:
    """Filter + layer configuration for the map."""
    layer: str = "vulnerability"  # "vulnerability" | "shock"
    modes_enabled: set = field(default_factory=lambda: {"air", "ocean", "truck"})
    lane_types_enabled: set = field(default_factory=lambda: {
        "inbound_component", "outbound_finished", "service_parts",
        # intra_region_distribution off by default — no arcs to draw
    })
    show_intra_region: bool = False
    show_top_only: bool = False  # Only show top 25% by current metric
    show_hotspots: bool = True


# Internal — a single drawable lane after projection
@dataclass
class _LaneVisual:
    lane_id: str
    origin_region: str
    dest_region: str
    sub_mode: str
    mode: str
    lane_type: str
    annual_cost: float
    metric_value: float        # the value used for color (structural exposure or company net)
    is_filtered_out: bool      # if True, draw with FLOW_DIM_OPACITY
    arc_segments: list         # list of QPainterPath segments (1 normally, 2 if antimeridian-split)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class WorldFlowMap(QWidget):
    """Custom-painted world map with flow arcs."""

    # Emitted when user clicks a lane (lane_id passed)
    lane_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(420)
        self.setMouseTracking(True)
        self.setStyleSheet(f"background:{theme.BG_RAISED};")

        self._diagnostic = None
        self._shock_result = None
        self._region_anchors: pd.DataFrame | None = None
        self._options = MapOptions()

        # Cache: list of _LaneVisual (recomputed on data change)
        self._lane_visuals: List[_LaneVisual] = []
        # Cache: region_code → (lng, lat, total_cost, n_lanes_at)
        self._anchors_cache: dict = {}
        # Currently hovered lane (for highlight)
        self._hovered_lane_id: str | None = None

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def set_data(self, diagnostic, shock_result, region_anchors: pd.DataFrame,
                 options: MapOptions | None = None):
        """Set the data + options in one call. Triggers full recompute."""
        self._diagnostic = diagnostic
        self._shock_result = shock_result
        self._region_anchors = region_anchors
        if options is not None:
            self._options = options
        self._recompute()
        self.update()

    def set_options(self, options: MapOptions):
        """Update filter/layer options without changing data."""
        self._options = options
        self._recompute()
        self.update()

    def set_shock_result(self, shock_result):
        """Refresh shock-layer color when controller's shock changes."""
        self._shock_result = shock_result
        if self._options.layer == "shock":
            self._recompute()
            self.update()

    def get_filtered_lanes(self) -> List[dict]:
        """Return lanes currently passing filters, sorted desc by metric value.

        Used by Page 2's "top lanes" table. Returns plain dicts so the table
        doesn't depend on internal types.
        """
        rows = []
        for lv in self._lane_visuals:
            if lv.is_filtered_out:
                continue
            rows.append({
                "lane_id": lv.lane_id,
                "od": f"{lv.origin_region}→{lv.dest_region}",
                "sub_mode": lv.sub_mode,
                "lane_type": lv.lane_type,
                "annual_cost": lv.annual_cost,
                "metric_value": lv.metric_value,
            })
        rows.sort(key=lambda r: -abs(r["metric_value"]))
        return rows

    # -------------------------------------------------------------------
    # Projection
    # -------------------------------------------------------------------

    def _project(self, lng: float, lat: float) -> Tuple[float, float]:
        """Equirectangular projection: (lng, lat) → (x, y) in widget coords."""
        rect = self._map_rect()
        x = rect.left() + (lng - LNG_MIN) / (LNG_MAX - LNG_MIN) * rect.width()
        # latitude inverted (y axis points down in Qt)
        y = rect.top() + (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * rect.height()
        return x, y

    def _map_rect(self) -> QRectF:
        return QRectF(
            PADDING_LR, PADDING_TB,
            self.width() - 2 * PADDING_LR,
            self.height() - 2 * PADDING_TB,
        )

    # -------------------------------------------------------------------
    # Recompute lane visuals (after data or options change)
    # -------------------------------------------------------------------

    def _recompute(self):
        """Project lane endpoints, build arcs, evaluate filters."""
        self._lane_visuals.clear()
        self._anchors_cache.clear()

        if self._diagnostic is None or self._region_anchors is None:
            return

        anchors = {row["region_code"]: (float(row["longitude"]),
                                        float(row["latitude"]))
                   for _, row in self._region_anchors.iterrows()}

        lanes_df = self._diagnostic.lanes.copy()

        # Choose the metric column
        if self._options.layer == "shock" and self._shock_result is not None:
            shock_lanes = self._shock_result.lanes.set_index("lane_id")
            lanes_df = lanes_df.set_index("lane_id")
            lanes_df["metric_value"] = shock_lanes["company_net_steady_state_usd"]
            lanes_df = lanes_df.reset_index()
        else:
            lanes_df["metric_value"] = lanes_df["structural_exposure_usd"]

        # Determine the max metric value for color normalization
        # Use absolute values so negative shocks (price relief) still color correctly
        if len(lanes_df) > 0:
            max_metric = max(1.0, lanes_df["metric_value"].abs().max())
            max_cost = max(1.0, lanes_df["annual_transportation_cost_usd"].max())
        else:
            max_metric = 1.0
            max_cost = 1.0

        # If "top only" mode, find the cutoff
        cutoff_value = 0.0
        if self._options.show_top_only and len(lanes_df) > 0:
            cutoff_value = float(lanes_df["metric_value"].abs().quantile(0.75))

        # Build per-region cost totals for anchor sizing
        region_cost = {}
        region_count = {}
        for _, lane in lanes_df.iterrows():
            for region in (lane["origin_region"], lane["destination_region"]):
                region_cost[region] = region_cost.get(region, 0) + float(
                    lane["annual_transportation_cost_usd"]
                )
                region_count[region] = region_count.get(region, 0) + 1
        max_region_cost = max(region_cost.values()) if region_cost else 1.0

        for code, (lng, lat) in anchors.items():
            self._anchors_cache[code] = {
                "lng": lng, "lat": lat,
                "cost": region_cost.get(code, 0),
                "count": region_count.get(code, 0),
                "max_cost": max_region_cost,
            }

        # Now build lane visuals
        for _, lane in lanes_df.iterrows():
            lane_type = lane["lane_type"]
            mode = lane["mode"]
            o_code = lane["origin_region"]
            d_code = lane["destination_region"]
            metric = float(lane["metric_value"])
            cost = float(lane["annual_transportation_cost_usd"])

            # intra-region: no arcs to draw, even when enabled
            if lane_type == "intra_region_distribution":
                continue
            # Skip self-loops in non-intra cases (rare same-region lanes for inbound)
            if o_code == d_code:
                continue

            # Filter evaluation
            mode_pass = mode in self._options.modes_enabled
            type_pass = lane_type in self._options.lane_types_enabled
            top_pass = (not self._options.show_top_only) or abs(metric) >= cutoff_value
            is_filtered_out = not (mode_pass and type_pass and top_pass)

            # Project endpoints
            o_lng, o_lat = anchors[o_code]
            d_lng, d_lat = anchors[d_code]
            o_x, o_y = self._project(o_lng, o_lat)
            d_x, d_y = self._project(d_lng, d_lat)

            # Detect antimeridian crossing
            lng_diff = d_lng - o_lng
            crosses_antimeridian = abs(lng_diff) > 180

            arc_segments: list = []
            if not crosses_antimeridian:
                # Single arc, simple curve
                arc_segments.append(self._build_arc((o_x, o_y), (d_x, d_y)))
            else:
                # Split into two arcs that wrap around
                # Determine direction: shorter path goes "outward" via the antimeridian
                if lng_diff > 0:
                    # e.g., -150 → +150: shorter path goes leftward through -180
                    # First segment: origin → left edge at intermediate lat
                    lat_at_edge = o_lat + (d_lat - o_lat) * abs((-180 - o_lng) /
                                                                  (lng_diff - 360))
                    edge_left_x, edge_left_y = self._project(-180, lat_at_edge)
                    edge_right_x, edge_right_y = self._project(180, lat_at_edge)
                    arc_segments.append(self._build_arc((o_x, o_y),
                                                         (edge_left_x, edge_left_y)))
                    arc_segments.append(self._build_arc((edge_right_x, edge_right_y),
                                                         (d_x, d_y)))
                else:
                    # e.g., +150 → -150: shorter path goes rightward through +180
                    lat_at_edge = o_lat + (d_lat - o_lat) * abs((180 - o_lng) /
                                                                  (lng_diff + 360))
                    edge_left_x, edge_left_y = self._project(-180, lat_at_edge)
                    edge_right_x, edge_right_y = self._project(180, lat_at_edge)
                    arc_segments.append(self._build_arc((o_x, o_y),
                                                         (edge_right_x, edge_right_y)))
                    arc_segments.append(self._build_arc((edge_left_x, edge_left_y),
                                                         (d_x, d_y)))

            self._lane_visuals.append(_LaneVisual(
                lane_id=lane["lane_id"],
                origin_region=o_code,
                dest_region=d_code,
                sub_mode=lane["sub_mode"],
                mode=mode,
                lane_type=lane_type,
                annual_cost=cost,
                metric_value=metric,
                is_filtered_out=is_filtered_out,
                arc_segments=arc_segments,
            ))

        # Cache normalization values for use in paintEvent
        self._max_metric = max_metric
        self._max_cost = max_cost

    def _build_arc(self, start: Tuple[float, float],
                   end: Tuple[float, float]) -> QPainterPath:
        """Build a smooth Bezier curve from start to end, arcing upward."""
        sx, sy = start
        ex, ey = end

        # Midpoint of straight line
        mx = (sx + ex) / 2
        my = (sy + ey) / 2

        # Distance for arc curvature
        dx = ex - sx
        dy = ey - sy
        dist = sqrt(dx * dx + dy * dy)

        # Perpendicular offset proportional to distance, but capped
        # (so very long lines don't arc too dramatically)
        offset = min(dist * 0.2, 80)

        # Direction perpendicular to line, "up" (negative y)
        # Normalize the perpendicular (-dy, dx)
        if dist > 0:
            nx = -dy / dist
            ny = dx / dist
        else:
            nx, ny = 0, -1

        # Always arc upward visually (i.e., negative y direction in Qt coords)
        if ny > 0:
            nx, ny = -nx, -ny

        ctrl_x = mx + nx * offset
        ctrl_y = my + ny * offset

        path = QPainterPath()
        path.moveTo(sx, sy)
        path.quadTo(ctrl_x, ctrl_y, ex, ey)
        return path

    # -------------------------------------------------------------------
    # Paint
    # -------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Background
        painter.fillRect(self.rect(), QColor(theme.BG_RAISED))

        # Coastlines
        self._paint_coastlines(painter)

        # Hotspots (drawn under flows)
        if self._options.show_hotspots:
            self._paint_hotspots(painter)

        # Flow lanes (filtered-out first, then active, then hovered)
        self._paint_flows(painter, only_filtered_out=True)
        self._paint_flows(painter, only_filtered_out=False)

        # Region anchors
        self._paint_anchors(painter)

        # Region labels
        self._paint_region_labels(painter)

    def _paint_coastlines(self, painter: QPainter):
        painter.setPen(QPen(COASTLINE_STROKE, 0.6))
        painter.setBrush(QBrush(COASTLINE_FILL))
        for poly in WORLD_POLYGONS:
            qpoly = QPolygonF()
            for lng, lat in poly:
                # Clip latitudes to our visible window
                lat_clipped = max(LAT_MIN, min(LAT_MAX, lat))
                x, y = self._project(lng, lat_clipped)
                qpoly.append(QPointF(x, y))
            painter.drawPolygon(qpoly)

    def _paint_hotspots(self, painter: QPainter):
        font = QFont(painter.font())
        font.setPointSize(theme.FONT_SIZE_TINY)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        for lng, lat, color, label in HOTSPOTS:
            x, y = self._project(lng, lat)
            # Pulsing ring (just a circle for now, two-tone)
            outer = QColor(color)
            outer.setAlpha(70)
            painter.setBrush(QBrush(outer))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x, y), 9, 9)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), 3, 3)
            # Label with stronger contrast
            painter.setPen(QColor(theme.TEXT_SECONDARY))
            painter.drawText(int(x + 8), int(y - 8), label)

    def _paint_flows(self, painter: QPainter, only_filtered_out: bool):
        if not self._lane_visuals:
            return
        for lv in self._lane_visuals:
            if lv.is_filtered_out != only_filtered_out:
                continue
            # Color from metric, normalized
            t = abs(lv.metric_value) / self._max_metric if self._max_metric > 0 else 0
            color = severity_color(t)

            # Width from cost
            w_norm = lv.annual_cost / self._max_cost if self._max_cost > 0 else 0
            width = FLOW_MIN_WIDTH + (FLOW_MAX_WIDTH - FLOW_MIN_WIDTH) * sqrt(w_norm)

            # Opacity
            if lv.is_filtered_out:
                color.setAlphaF(FLOW_DIM_OPACITY)
            elif lv.lane_id == self._hovered_lane_id:
                # full opacity, slightly thicker
                width = width + 1.5
            else:
                color.setAlphaF(0.85)

            pen = QPen(color, width)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for seg in lv.arc_segments:
                painter.drawPath(seg)

    def _paint_anchors(self, painter: QPainter):
        if not self._anchors_cache:
            return
        for code, info in self._anchors_cache.items():
            x, y = self._project(info["lng"], info["lat"])
            cost = info["cost"]
            max_c = info["max_cost"]
            t = sqrt(cost / max_c) if max_c > 0 else 0
            radius = ANCHOR_MIN_RADIUS + (ANCHOR_MAX_RADIUS - ANCHOR_MIN_RADIUS) * t

            # Outer glow
            glow = QColor(theme.ACCENT_PRIMARY)
            glow.setAlpha(30)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(x, y), radius + 4, radius + 4)

            # Solid anchor
            painter.setBrush(QBrush(QColor(theme.ACCENT_PRIMARY)))
            painter.setPen(QPen(ANCHOR_BORDER, ANCHOR_BORDER_WIDTH))
            painter.drawEllipse(QPointF(x, y), radius, radius)

    def _paint_region_labels(self, painter: QPainter):
        if not self._anchors_cache or self._region_anchors is None:
            return
        anchor_city = dict(zip(self._region_anchors["region_code"],
                                self._region_anchors["anchor_city"]))
        font = QFont(painter.font())
        font.setPointSize(theme.FONT_SIZE_SMALL)
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_PRIMARY))
        for code, info in self._anchors_cache.items():
            x, y = self._project(info["lng"], info["lat"])
            radius = ANCHOR_MAX_RADIUS
            text = f"{code}"
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(text)
            painter.drawText(int(x - text_w / 2), int(y - radius - 6), text)

    # -------------------------------------------------------------------
    # Hover / tooltip
    # -------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        pos = event.pos()
        hovered = self._find_lane_under(pos)
        if hovered != self._hovered_lane_id:
            self._hovered_lane_id = hovered
            self.update()

        if hovered is not None:
            lv = next((l for l in self._lane_visuals if l.lane_id == hovered), None)
            if lv is not None:
                metric_label = ("Structural exposure"
                                 if self._options.layer == "vulnerability"
                                 else "Company net (steady-state)")
                tooltip = (
                    f"<b>{lv.lane_id}</b>  {lv.origin_region}→{lv.dest_region}<br>"
                    f"{lv.sub_mode.replace('_', ' ')} · "
                    f"{lv.lane_type.replace('_', ' ')}<br>"
                    f"Annual cost: ${lv.annual_cost / 1e6:.1f}M<br>"
                    f"{metric_label}: ${lv.metric_value / 1e6:.2f}M"
                )
                QToolTip.showText(event.globalPos(), tooltip, self)
            else:
                QToolTip.hideText()
        else:
            QToolTip.hideText()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            hovered = self._find_lane_under(event.pos())
            if hovered is not None:
                self.lane_clicked.emit(hovered)

    def _find_lane_under(self, pos) -> Optional[str]:
        """Find the lane whose arc passes nearest to pos. Returns lane_id or None."""
        if not self._lane_visuals:
            return None
        # Precise hit-testing over Bezier paths is expensive; use bounding-box prune
        # plus a sampling-based distance check
        px, py = pos.x(), pos.y()
        best_lane = None
        best_dist = 8.0  # tolerance in pixels
        for lv in self._lane_visuals:
            if lv.is_filtered_out:
                continue
            for seg in lv.arc_segments:
                bbox = seg.boundingRect()
                if not bbox.adjusted(-8, -8, 8, 8).contains(QPointF(px, py)):
                    continue
                # Sample 20 points along the path
                for i in range(21):
                    t = i / 20
                    pt = seg.pointAtPercent(t)
                    dx = pt.x() - px
                    dy = pt.y() - py
                    d = sqrt(dx * dx + dy * dy)
                    if d < best_dist:
                        best_dist = d
                        best_lane = lv.lane_id
                        break
        return best_lane

    def leaveEvent(self, event):
        if self._hovered_lane_id is not None:
            self._hovered_lane_id = None
            self.update()
        QToolTip.hideText()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        # Re-project everything when window resizes
        if self._diagnostic is not None:
            self._recompute()
        super().resizeEvent(event)
