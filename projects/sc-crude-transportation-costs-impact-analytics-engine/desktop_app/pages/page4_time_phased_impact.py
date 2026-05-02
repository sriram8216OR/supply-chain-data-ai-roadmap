"""
Page 4 — Time-Phased Impact.

Strategic question: how does exposure unfold in time, and what are the levers
to act early?

Layout (top to bottom):
  - Description
  - Headline strip: 3 timing metrics (first impact wk, steady-state wk, % by wk 8)
  - Slice selector (mode / lane_type / archetype / sub_mode)
  - Cumulative + incremental dual chart
  - Top 10 early-impact lanes callout
  - Lane drill-down: table + per-lane share-by-share staircase
  - Auto insight footer

Page only renders meaningfully when shock != 0. If shock == 0, displays
empty-state prompt directing user to the sidebar slider.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from .. import theme
from ..controller import AppController
from ..widgets.formatting import fmt_usd
from ..widgets.headline_number import HeadlineNumber
from ..widgets.insight_box import InsightBox
from ..widgets.stacked_area_chart import AreaSeries, StackedAreaChart
from ..widgets.time_phased_dual_chart import StackSeries, TimePhasedDualChart


# Slice options (id, label, curve_attr_name, color_map)
SLICE_OPTIONS = [
    ("mode", "Mode", "by_mode_curve",
     ["air", "ocean", "truck"], None),
    ("lane_type", "Lane type", "by_lane_type_curve",
     ["inbound_component", "outbound_finished",
      "service_parts", "intra_region_distribution"], None),
    ("archetype", "Contract archetype", "by_archetype_curve",
     ["spot", "indexed_short", "indexed_medium", "baf_long", "fixed"], None),
    ("sub_mode", "Sub-mode", "by_sub_mode_curve",
     None, None),  # sub_modes vary; we'll auto-discover
]


SLICE_QSS = f"""
QPushButton#chip {{
    background-color: {theme.BG_RAISED};
    color: {theme.TEXT_SECONDARY};
    padding: 6px 14px;
    border: 1px solid {theme.BORDER_SUBTLE};
    border-radius: 12px;
    font-size: {theme.FONT_SIZE_SMALL}px;
}}
QPushButton#chip:hover {{
    border-color: {theme.BORDER_STRONG};
    color: {theme.TEXT_PRIMARY};
}}
QPushButton#chip:checked {{
    background-color: {theme.ACCENT_PRIMARY};
    color: white;
    border-color: {theme.ACCENT_PRIMARY};
}}
"""


class Page4TimePhasedImpact(QWidget):
    def __init__(self, controller: AppController):
        super().__init__()
        self._controller = controller
        self._slice_id = "mode"
        self._slice_buttons: dict[str, QPushButton] = {}
        self._selected_lane_id: Optional[str] = None

        self._build_ui()
        self._populate()

        self._controller.shock_changed.connect(self._on_shock_changed)

    # -------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------

    def _build_ui(self):
        # We use a QStackedWidget at the top level: one page for empty state, one for content
        self._stack = QStackedWidget()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._stack)

        # Empty state
        self._empty_state = self._build_empty_state()
        self._stack.addWidget(self._empty_state)

        # Real content (scrollable)
        self._content = self._build_content()
        self._stack.addWidget(self._content)

    def _build_empty_state(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(theme.SPACING_MD)

        icon = QLabel("⏱")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            f"color:{theme.TEXT_MUTED}; font-size:48px;"
        )
        layout.addWidget(icon)

        title = QLabel("Set a non-zero Brent shock to see time dynamics")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color:{theme.TEXT_PRIMARY}; "
            f"font-size:{theme.FONT_SIZE_HEADING}px; "
            f"font-weight:500;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "This page shows how exposure unfolds week-by-week.\n"
            "Adjust the Δ Brent slider in the sidebar to apply a shock."
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; "
            f"font-size:{theme.FONT_SIZE_BASE}px;"
        )
        layout.addWidget(subtitle)

        return w

    def _build_content(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background:{theme.BG_BASE};")

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_LG,
        )
        layout.setSpacing(theme.SPACING_MD)

        # Description
        self._description = QLabel()
        self._description.setObjectName("section_caption")
        self._description.setWordWrap(True)
        self._description.setTextFormat(Qt.RichText)
        layout.addWidget(self._description)

        # Headline strip
        layout.addWidget(self._build_headline_strip())

        # Slice selector
        layout.addWidget(self._build_slice_selector())

        # Dual chart
        layout.addLayout(self._build_chart_section())

        # Early-impact callout
        layout.addLayout(self._build_early_impact_section())

        # Lane drill-down
        layout.addLayout(self._build_drill_down_section())

        # Insight
        self._insight = InsightBox()
        layout.addWidget(self._insight)

        layout.addStretch(1)
        return scroll

    def _build_headline_strip(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.SPACING_MD)

        self._hl_first = HeadlineNumber("First Impact Week")
        self._hl_steady = HeadlineNumber("Steady State Week")
        self._hl_by_8 = HeadlineNumber("Materialized by Week 8")

        row.addWidget(self._hl_first, 1)
        row.addWidget(self._hl_steady, 1)
        row.addWidget(self._hl_by_8, 1)
        return wrap

    def _build_slice_selector(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet(panel.styleSheet() + SLICE_QSS)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_SM,
            theme.SPACING_LG, theme.SPACING_SM,
        )
        layout.setSpacing(theme.SPACING_SM)

        label = QLabel("SLICE BY")
        label.setObjectName("fp_label")
        layout.addWidget(label)

        self._slice_group = QButtonGroup(self)
        self._slice_group.setExclusive(True)
        for slice_id, label_text, _, _, _ in SLICE_OPTIONS:
            btn = QPushButton(label_text)
            btn.setObjectName("chip")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, s=slice_id: self._on_slice_changed(s))
            self._slice_buttons[slice_id] = btn
            self._slice_group.addButton(btn)
            layout.addWidget(btn)
        self._slice_buttons[self._slice_id].setChecked(True)

        layout.addStretch(1)
        return panel

    def _build_chart_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        self._chart_heading = QLabel("Cumulative + weekly increments")
        self._chart_heading.setObjectName("section_heading")
        wrap.addWidget(self._chart_heading)

        self._chart_caption = QLabel()
        self._chart_caption.setObjectName("section_caption")
        self._chart_caption.setWordWrap(True)
        self._chart_caption.setTextFormat(Qt.RichText)
        wrap.addWidget(self._chart_caption)

        # Legend strip (color swatches with labels)
        self._legend_widget = QFrame()
        self._legend_layout = QHBoxLayout(self._legend_widget)
        self._legend_layout.setContentsMargins(0, 0, 0, 0)
        self._legend_layout.setSpacing(theme.SPACING_MD)
        wrap.addWidget(self._legend_widget)

        # Chart panel
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_SM, theme.SPACING_SM,
            theme.SPACING_SM, theme.SPACING_SM,
        )
        self._chart = TimePhasedDualChart()
        panel_layout.addWidget(self._chart)
        wrap.addWidget(panel)
        return wrap

    def _build_early_impact_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Early-impact lanes (top 10 lanes flipping by week 4)")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        caption = QLabel(
            "These lanes are the levers for early action — short-cycle resets that "
            "absorb shock pressure quickly. Renegotiating any of these before the shock "
            "lands could materially blunt the early pulse."
        )
        caption.setObjectName("section_caption")
        caption.setWordWrap(True)
        wrap.addWidget(caption)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )

        self._early_table = QTableWidget(10, 6)
        self._early_table.setHorizontalHeaderLabels(
            ["Lane", "O→D", "Sub-mode", "Type", "First impact week", "Company net"]
        )
        self._early_table.verticalHeader().setVisible(False)
        self._early_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._early_table.setSelectionMode(QTableWidget.NoSelection)
        self._early_table.setShowGrid(False)
        self._early_table.setStyleSheet(self._table_qss())
        self._early_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._early_table.horizontalHeader().setStretchLastSection(True)
        self._early_table.setFixedHeight(280)
        panel_layout.addWidget(self._early_table)
        wrap.addWidget(panel)
        return wrap

    def _build_drill_down_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Lane drill-down")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        caption = QLabel(
            "All lanes with company net exposure under current shock, sorted by company net. "
            "Click a row to see that lane's share-by-share staircase below — each share "
            "(provider/archetype combination) is plotted as a separate area."
        )
        caption.setObjectName("section_caption")
        caption.setWordWrap(True)
        wrap.addWidget(caption)

        # Table
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )
        panel_layout.setSpacing(theme.SPACING_MD)

        self._lane_table = QTableWidget(0, 7)
        self._lane_table.setHorizontalHeaderLabels(
            ["Lane", "O→D", "Sub-mode", "Type", "First impact wk",
             "Steady state wk", "Company net"]
        )
        self._lane_table.verticalHeader().setVisible(False)
        self._lane_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._lane_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._lane_table.setSelectionMode(QTableWidget.SingleSelection)
        self._lane_table.setShowGrid(False)
        self._lane_table.setStyleSheet(self._table_qss())
        self._lane_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._lane_table.horizontalHeader().setStretchLastSection(True)
        self._lane_table.setFixedHeight(320)
        self._lane_table.itemSelectionChanged.connect(self._on_lane_selected)
        panel_layout.addWidget(self._lane_table)

        # Per-lane chart
        self._lane_chart_label = QLabel("Select a lane above to see its share-by-share staircase")
        self._lane_chart_label.setStyleSheet(
            f"color:{theme.TEXT_MUTED}; font-size:{theme.FONT_SIZE_SMALL}px;"
        )
        panel_layout.addWidget(self._lane_chart_label)

        self._lane_chart = StackedAreaChart()
        self._lane_chart.setMinimumHeight(260)
        panel_layout.addWidget(self._lane_chart)

        wrap.addWidget(panel)
        return wrap

    def _table_qss(self) -> str:
        return f"""
            QTableWidget {{
                background:{theme.BG_RAISED};
                color:{theme.TEXT_PRIMARY};
                border:none;
                font-family: {theme.FONT_FAMILY_MONO};
                font-size: {theme.FONT_SIZE_SMALL}px;
                gridline-color: {theme.BORDER_SUBTLE};
            }}
            QTableWidget::item {{ padding: 4px 8px; }}
            QTableWidget::item:selected {{
                background:{theme.BG_HIGHLIGHT};
                color:{theme.TEXT_PRIMARY};
            }}
            QHeaderView::section {{
                background:{theme.BG_RAISED};
                color:{theme.TEXT_LABEL};
                border:none;
                border-bottom:1px solid {theme.BORDER_SUBTLE};
                padding:6px 8px;
                font-family: {theme.FONT_FAMILY_BASE};
                font-size: {theme.FONT_SIZE_TINY}px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }}
        """

    # -------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------

    def _on_slice_changed(self, slice_id: str):
        self._slice_id = slice_id
        self._refresh_chart()
        self._refresh_chart_caption()

    def _on_shock_changed(self, shock_result):
        self._populate()

    def _on_lane_selected(self):
        rows = self._lane_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        lane_id_item = self._lane_table.item(row, 0)
        if lane_id_item:
            self._selected_lane_id = lane_id_item.text()
            self._refresh_lane_drilldown()

    # -------------------------------------------------------------------
    # Data population
    # -------------------------------------------------------------------

    def _populate(self):
        delta = self._controller.delta_brent
        if delta == 0:
            self._stack.setCurrentIndex(0)  # show empty state
            return

        self._stack.setCurrentIndex(1)  # show content
        shock = self._controller.shock_result

        # Description
        sign = "+" if delta > 0 else ""
        direction = "upward" if delta > 0 else "downward"
        self._description.setText(
            f"Sustained <b>{direction}</b> Brent shock of <b>{sign}${delta:.0f}/bbl</b> "
            "applied. Time dynamics show how exposure unfolds — from first contract resets "
            "through steady state — with weekly increment bars revealing each pulse."
        )

        # Headline metrics
        first_impact = shock.first_company_impact_week
        steady = shock.steady_state_week
        net_curve = shock.network_curve.values
        total_net = shock.total_company_net_steady_state_usd

        self._hl_first.set_value(f"wk {first_impact}" if first_impact > 0 else "—")
        self._hl_first.set_subtext("Earliest contract reset")
        self._hl_steady.set_value(f"wk {steady}" if steady > 0 else "—")
        self._hl_steady.set_subtext("All horizon contracts reset")

        if total_net != 0 and len(net_curve) > 8:
            pct_by_8 = net_curve[8] / total_net * 100
            self._hl_by_8.set_value(f"{pct_by_8:.0f}%")
            self._hl_by_8.set_subtext(f"of {fmt_usd(total_net, 'M')} steady state")
        else:
            self._hl_by_8.set_value("—")
            self._hl_by_8.set_subtext("")

        # Refresh chart with current slice
        self._refresh_chart()
        self._refresh_chart_caption()

        # Early-impact callout
        self._populate_early_impact(shock)

        # Lane drill-down table
        self._populate_lane_table(shock)

        # If a lane was previously selected and still exists, refresh its chart
        if self._selected_lane_id is not None:
            self._refresh_lane_drilldown()

        # Insight
        self._populate_insight(shock)

    def _refresh_chart(self):
        delta = self._controller.delta_brent
        if delta == 0:
            return
        shock = self._controller.shock_result

        slice_id, label_text, attr, ordered_keys, _ = next(
            opt for opt in SLICE_OPTIONS if opt[0] == self._slice_id
        )
        curve_df: pd.DataFrame = getattr(shock, attr)
        weeks = np.array(curve_df.index, dtype=float)

        # Determine column order and colors
        color_map = {}
        if slice_id == "mode":
            keys = ordered_keys
            color_map = {k: theme.MODE_COLORS[k] for k in keys}
        elif slice_id == "lane_type":
            keys = [k for k in ordered_keys if k in curve_df.columns]
            color_map = {k: theme.LANE_TYPE_COLORS[k] for k in keys}
        elif slice_id == "archetype":
            keys = [k for k in ordered_keys if k in curve_df.columns]
            color_map = {k: theme.ARCHETYPE_COLORS[k] for k in keys}
        else:  # sub_mode
            keys = sorted(curve_df.columns,
                          key=lambda k: -curve_df[k].iloc[-1])  # by total at end, descending
            # Use mode parent colors with slight variation
            sub_mode_colors = {
                "air_widebody": "#E94B5C",
                "air_narrowbody": "#F08490",
                "ocean_ulcv": "#3D6CB8",
                "ocean_panamax": "#5B8DEF",
                "ocean_feeder": "#7FA9F4",
                "truck_longhaul": "#5C8A4F",
                "truck_shorthaul": "#8AB57E",
            }
            color_map = {k: sub_mode_colors.get(k, theme.ACCENT_PRIMARY) for k in keys}

        # Filter out keys that contribute zero across all weeks
        keys_nonzero = [k for k in keys if curve_df[k].iloc[-1] > 0]

        series_list = []
        for k in keys_nonzero:
            series_list.append(StackSeries(
                label=k,
                values=curve_df[k].to_numpy().astype(float),
                color=color_map[k],
            ))

        self._chart.set_data(
            weeks=weeks,
            series_list=series_list,
            first_impact_week=shock.first_company_impact_week,
            steady_state_week=shock.steady_state_week,
        )

        # Refresh legend
        self._refresh_legend(keys_nonzero, color_map)

    def _refresh_legend(self, keys: list[str], color_map: dict[str, str]):
        # Clear existing legend items
        while self._legend_layout.count():
            item = self._legend_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for k in keys:
            item_widget = QWidget()
            h = QHBoxLayout(item_widget)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(theme.SPACING_XS)

            swatch = QFrame()
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(f"background:{color_map[k]}; border-radius:2px;")
            h.addWidget(swatch)

            text = QLabel(k.replace("_", " "))
            text.setStyleSheet(
                f"color:{theme.TEXT_SECONDARY}; "
                f"font-size:{theme.FONT_SIZE_SMALL}px;"
            )
            h.addWidget(text)
            self._legend_layout.addWidget(item_widget)

        self._legend_layout.addStretch(1)

    def _refresh_chart_caption(self):
        slice_id, label_text, _, _, _ = next(
            opt for opt in SLICE_OPTIONS if opt[0] == self._slice_id
        )
        self._chart_caption.setText(
            f"Top: cumulative company net exposure ($) over time, sliced by <b>{label_text.lower()}</b>. "
            "Bottom: weekly increment — the size of each pulse as it lands. "
            "The largest spikes are the moments where multiple shares reset simultaneously."
        )

    def _populate_early_impact(self, shock):
        lanes = shock.lanes.copy()
        # Lanes flipping by week 4 (inclusive) with non-zero company net
        early = lanes[
            (lanes["first_company_impact_week"] <= 4)
            & (lanes["first_company_impact_week"] > 0)
            & (lanes["company_net_steady_state_usd"].abs() > 0)
        ].copy()
        # Sort by company net desc
        early = early.assign(_abs=early["company_net_steady_state_usd"].abs())
        early = early.sort_values("_abs", ascending=False).head(10)

        if early.empty:
            self._early_table.setRowCount(1)
            placeholder = QTableWidgetItem("No lanes flip by week 4 under this shock")
            placeholder.setTextAlignment(Qt.AlignCenter)
            self._early_table.setItem(0, 0, placeholder)
            self._early_table.setSpan(0, 0, 1, 6)
            return

        self._early_table.clearSpans()
        self._early_table.setRowCount(len(early))
        for i, (_, row) in enumerate(early.iterrows()):
            cells = [
                row["lane_id"],
                f"{row['origin_region']}→{row['destination_region']}",
                row["sub_mode"].replace("_", " "),
                row["lane_type"].replace("_", " "),
                f"wk {int(row['first_company_impact_week'])}",
                fmt_usd(float(row["company_net_steady_state_usd"]), "M"),
            ]
            for j, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if j in (4, 5):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._early_table.setItem(i, j, item)

    def _populate_lane_table(self, shock):
        lanes = shock.lanes.copy()
        # All lanes with company net > 0
        active = lanes[lanes["company_net_steady_state_usd"].abs() > 0].copy()
        active = active.assign(_abs=active["company_net_steady_state_usd"].abs())
        active = active.sort_values("_abs", ascending=False)

        # Block selection signal during repopulate
        self._lane_table.blockSignals(True)
        self._lane_table.setRowCount(len(active))
        for i, (_, row) in enumerate(active.iterrows()):
            cells = [
                row["lane_id"],
                f"{row['origin_region']}→{row['destination_region']}",
                row["sub_mode"].replace("_", " "),
                row["lane_type"].replace("_", " "),
                f"wk {int(row['first_company_impact_week'])}",
                f"wk {int(row['steady_state_week'])}",
                fmt_usd(float(row["company_net_steady_state_usd"]), "M"),
            ]
            for j, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if j in (4, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._lane_table.setItem(i, j, item)
        self._lane_table.blockSignals(False)

    def _refresh_lane_drilldown(self):
        if self._selected_lane_id is None:
            return
        delta = self._controller.delta_brent
        if delta == 0:
            return
        shock = self._controller.shock_result
        contributions = shock.lane_share_contributions.get(self._selected_lane_id, [])
        if not contributions:
            self._lane_chart_label.setText(
                f"Lane {self._selected_lane_id}: no shares with non-zero impact"
            )
            self._lane_chart.set_data(
                weeks=np.array([0, shock.horizon_weeks]),
                series_list=[],
            )
            return

        # Build a stacked series — one series per (provider, archetype) share with
        # non-zero contribution. The cumulative value of each share is 0 before flip_week,
        # then constant share_company_net thereafter.
        weeks = np.arange(shock.horizon_weeks + 1)

        # Filter out fixed contracts (zero pass-through, never contribute)
        active = [c for c in contributions if c["share_company_net"] > 0
                  and c["flip_week"] <= shock.horizon_weeks]
        if not active:
            self._lane_chart_label.setText(
                f"Lane {self._selected_lane_id}: all contracts outside horizon "
                f"(likely fixed-contract dominant)"
            )
            self._lane_chart.set_data(
                weeks=weeks.astype(float),
                series_list=[],
            )
            return

        # Sort by flip_week (earliest first) so colors stack consistently
        active.sort(key=lambda c: c["flip_week"])

        # Build series; use distinct colors based on archetype
        series_list = []
        for c in active:
            arch = c["archetype"]
            color = theme.ARCHETYPE_COLORS.get(arch, theme.ACCENT_PRIMARY)
            vals = np.zeros(len(weeks))
            vals[c["flip_week"]:] = c["share_company_net"]
            label = f"{c['provider']} ({arch.replace('_', ' ')})"
            series_list.append(AreaSeries(
                label=label,
                values=vals,
                color=color,
            ))

        # Find this lane's row in the lanes table to also annotate first/steady weeks
        lane_row = shock.lanes[shock.lanes["lane_id"] == self._selected_lane_id]
        first_wk = int(lane_row["first_company_impact_week"].iloc[0]) if len(lane_row) else 0
        steady_wk = int(lane_row["steady_state_week"].iloc[0]) if len(lane_row) else 0

        # Friendly title
        if len(lane_row):
            r = lane_row.iloc[0]
            self._lane_chart_label.setText(
                f"Lane <b>{self._selected_lane_id}</b> · "
                f"{r['origin_region']}→{r['destination_region']} · "
                f"{r['sub_mode'].replace('_', ' ')} · "
                f"{len(active)} contributing shares · "
                f"First impact wk {first_wk} → steady wk {steady_wk}"
            )
            self._lane_chart_label.setTextFormat(Qt.RichText)
        else:
            self._lane_chart_label.setText(f"Lane {self._selected_lane_id}")

        self._lane_chart.set_data(
            weeks=weeks.astype(float),
            series_list=series_list,
            first_impact_week=first_wk,
            steady_state_week=steady_wk if steady_wk != first_wk else 0,
        )

    def _populate_insight(self, shock):
        delta = shock.delta_brent_usd_per_bbl
        sign = "+" if delta > 0 else ""

        first = shock.first_company_impact_week
        steady = shock.steady_state_week
        total_net = shock.total_company_net_steady_state_usd
        net_curve = shock.network_curve.values

        if total_net == 0 or first == 0:
            self._insight.set_html(
                "No company net exposure under this shock — all flows fully insulated."
            )
            return

        pct_by_4 = net_curve[4] / total_net * 100 if len(net_curve) > 4 else 0
        pct_by_8 = net_curve[8] / total_net * 100 if len(net_curve) > 8 else 0
        pct_by_16 = net_curve[16] / total_net * 100 if len(net_curve) > 16 else 0

        # Most-contributing slice for the current view
        slice_id, label_text, attr, _, _ = next(
            opt for opt in SLICE_OPTIONS if opt[0] == self._slice_id
        )
        curve_df = getattr(shock, attr)
        end_values = curve_df.iloc[-1].sort_values(ascending=False)
        top_slice = end_values.index[0]
        top_share = end_values.iloc[0] / total_net * 100

        self._insight.set_html(
            f"Under {sign}${delta:.0f}/bbl Brent shock, exposure builds from "
            f"<b>{pct_by_4:.0f}%</b> by week 4, to <b>{pct_by_8:.0f}%</b> by week 8, "
            f"to <b>{pct_by_16:.0f}%</b> by week 16, reaching steady state "
            f"({fmt_usd(total_net, 'M')}) at week <b>{steady}</b>. "
            f"By {label_text.lower()}, <b>{top_slice.replace('_', ' ')}</b> contributes the "
            f"largest share at <b>{top_share:.0f}%</b> of company net."
        )
