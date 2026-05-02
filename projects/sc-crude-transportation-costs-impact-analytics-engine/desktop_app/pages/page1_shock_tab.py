"""
Tab 1.2 — Shock Impact Simulator.

Reads from controller.shock_result (recomputed on shock changes).
Subscribes to controller.shock_changed signal to refresh.

Layout:
  - Description (depends on direction of shock)
  - Shocked refined product prices (collapsible details)
  - Top strip: 3 headline numbers (gross, company net, provider absorbs)
  - Time-phased stacked area chart (by mode)
  - Lag distribution histogram + concentration callout
  - Auto-generated insight footer
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import theme
from ..controller import AppController
from ..widgets.formatting import fmt_usd
from ..widgets.headline_number import HeadlineNumber
from ..widgets.histogram import Histogram
from ..widgets.insight_box import InsightBox
from ..widgets.stacked_area_chart import AreaSeries, StackedAreaChart


class ShockTab(QWidget):
    def __init__(self, controller: AppController):
        super().__init__()
        self._controller = controller
        self._build_ui()
        self._populate(self._controller.shock_result)

        # Subscribe to shock changes
        self._controller.shock_changed.connect(self._populate)

    # -------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------

    def _build_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background:{theme.BG_BASE};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_LG,
        )
        layout.setSpacing(theme.SPACING_MD)

        # Description (dynamic based on shock direction)
        self._description = QLabel()
        self._description.setObjectName("section_caption")
        self._description.setWordWrap(True)
        self._description.setTextFormat(Qt.RichText)
        layout.addWidget(self._description)

        # Shocked prices panel
        layout.addLayout(self._build_shocked_prices_section())

        # Headline numbers
        layout.addWidget(self._build_headline_metrics())

        # Time-phased curve
        layout.addLayout(self._build_curve_section())

        # Lag distribution + concentration
        layout.addLayout(self._build_lag_concentration_row())

        # Insight box
        self._insight = InsightBox()
        layout.addWidget(self._insight)

        layout.addStretch(1)

    def _build_shocked_prices_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Shocked refined product prices")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        caption = QLabel(
            "How a Brent shock propagates to each refined product, using research-based "
            "elasticities. Bunker is closest to unity (least buffered); jet is least elastic."
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

        self._prices_table = QTableWidget(3, 5)
        self._prices_table.setHorizontalHeaderLabels(
            ["Refined product", "Elasticity", "Baseline ($/MT)", "Shocked ($/MT)", "% move"]
        )
        self._prices_table.verticalHeader().setVisible(False)
        self._prices_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._prices_table.setSelectionMode(QTableWidget.NoSelection)
        self._prices_table.setShowGrid(False)
        self._prices_table.setStyleSheet(f"""
            QTableWidget {{
                background:{theme.BG_RAISED};
                color:{theme.TEXT_PRIMARY};
                border:none;
                font-family: {theme.FONT_FAMILY_MONO};
                font-size: {theme.FONT_SIZE_SMALL}px;
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
        """)
        self._prices_table.horizontalHeader().setStretchLastSection(True)
        self._prices_table.setFixedHeight(120)
        panel_layout.addWidget(self._prices_table)
        wrap.addWidget(panel)
        return wrap

    def _build_headline_metrics(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.SPACING_MD)

        self._hl_gross = HeadlineNumber("Gross fuel exposure (system)")
        self._hl_company_net = HeadlineNumber("Company net (steady-state)")
        self._hl_provider = HeadlineNumber("Provider absorbs (steady-state)")

        row.addWidget(self._hl_gross, 1)
        row.addWidget(self._hl_company_net, 1)
        row.addWidget(self._hl_provider, 1)
        return wrap

    def _build_curve_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Time-phased company net exposure (cumulative, by mode)")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        caption = QLabel(
            "Each contract reset moves a piece of company net exposure from "
            "<i>provider absorbs</i> to <i>company pays</i>. The staircase rises "
            "as each share of each lane crosses its reset week."
        )
        caption.setObjectName("section_caption")
        caption.setWordWrap(True)
        caption.setTextFormat(Qt.RichText)
        wrap.addWidget(caption)

        # Legend
        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(0, 0, 0, 0)
        legend_row.setSpacing(theme.SPACING_MD)
        for mode in ["air", "ocean", "truck"]:
            item = self._make_legend_item(mode.title(), theme.MODE_COLORS[mode])
            legend_row.addWidget(item)
        legend_row.addStretch(1)
        wrap.addLayout(legend_row)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_SM, theme.SPACING_SM,
            theme.SPACING_SM, theme.SPACING_SM,
        )
        self._curve = StackedAreaChart()
        panel_layout.addWidget(self._curve)
        wrap.addWidget(panel)

        return wrap

    def _make_legend_item(self, label: str, color: str) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(theme.SPACING_XS)

        swatch = QFrame()
        swatch.setFixedSize(10, 10)
        swatch.setStyleSheet(f"background:{color}; border-radius:2px;")
        h.addWidget(swatch)

        text = QLabel(label)
        text.setStyleSheet(
            f"color:{theme.TEXT_SECONDARY}; font-size:{theme.FONT_SIZE_SMALL}px;"
        )
        h.addWidget(text)
        return w

    def _build_lag_concentration_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(theme.SPACING_MD)

        # Left: lag distribution
        lag_panel = QFrame()
        lag_panel.setObjectName("panel")
        lag_layout = QVBoxLayout(lag_panel)
        lag_layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )

        lag_heading = QLabel("Lag distribution: when does the impact land?")
        lag_heading.setObjectName("section_heading")
        lag_layout.addWidget(lag_heading)

        lag_caption = QLabel(
            "Company net exposure $ grouped by the week each lane first feels impact."
        )
        lag_caption.setObjectName("section_caption")
        lag_caption.setWordWrap(True)
        lag_layout.addWidget(lag_caption)

        self._histogram = Histogram()
        lag_layout.addWidget(self._histogram)

        # Right: concentration callout
        conc_panel = QFrame()
        conc_panel.setObjectName("panel")
        conc_layout = QVBoxLayout(conc_panel)
        conc_layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_LG,
            theme.SPACING_LG, theme.SPACING_LG,
        )
        conc_layout.setSpacing(theme.SPACING_MD)

        conc_heading = QLabel("Concentration")
        conc_heading.setObjectName("section_heading")
        conc_layout.addWidget(conc_heading)

        self._top_lane_label = QLabel()
        self._top_lane_label.setObjectName("fp_label")
        conc_layout.addWidget(self._top_lane_label)

        self._top_lane_value = QLabel()
        self._top_lane_value.setObjectName("headline_value")
        self._top_lane_value.setStyleSheet(
            f"font-family:{theme.FONT_FAMILY_MONO}; "
            f"font-size:{theme.FONT_SIZE_HEADING + 4}px; "
            f"color:{theme.TEXT_PRIMARY};"
        )
        conc_layout.addWidget(self._top_lane_value)

        self._top_lane_subtext = QLabel()
        self._top_lane_subtext.setObjectName("headline_subtext")
        self._top_lane_subtext.setWordWrap(True)
        conc_layout.addWidget(self._top_lane_subtext)

        conc_layout.addSpacing(theme.SPACING_SM)

        self._top5_label = QLabel("TOP 5 LANES SHARE OF COMPANY NET")
        self._top5_label.setObjectName("fp_label")
        conc_layout.addWidget(self._top5_label)

        self._top5_value = QLabel()
        self._top5_value.setObjectName("headline_value")
        self._top5_value.setStyleSheet(
            f"font-family:{theme.FONT_FAMILY_MONO}; "
            f"font-size:{theme.FONT_SIZE_HEADING + 4}px; "
            f"color:{theme.TEXT_PRIMARY};"
        )
        conc_layout.addWidget(self._top5_value)

        conc_layout.addStretch(1)

        row.addWidget(lag_panel, 3)
        row.addWidget(conc_panel, 2)
        return row

    # -------------------------------------------------------------------
    # Data population — re-runs every time shock changes
    # -------------------------------------------------------------------

    def _populate(self, shock):
        delta = shock.delta_brent_usd_per_bbl

        # Description
        if delta == 0:
            self._description.setText(
                "<b>Shock = 0.</b> Baseline scenario — no fuel cost change. "
                "Adjust the <b>Δ Brent</b> slider in the sidebar to simulate a sustained shock."
            )
        else:
            direction = "upward" if delta > 0 else "downward"
            sign = "+" if delta > 0 else ""
            self._description.setText(
                f"Sustained <b>{direction}</b> Brent shock of "
                f"<b>{sign}${delta:.0f}/bbl</b> on top of the April 2026 baseline of $104/bbl. "
                "All numbers are annualized at steady state."
            )

        # Shocked prices table
        self._populate_prices_table(shock.shocked_prices)

        # Headline metrics
        self._hl_gross.set_value(fmt_usd(shock.total_gross_exposure_usd, "M"))
        self._hl_gross.set_subtext("System absorbs total")

        self._hl_company_net.set_value(fmt_usd(shock.total_company_net_steady_state_usd, "M"))
        if shock.total_gross_exposure_usd != 0:
            net_share = shock.total_company_net_steady_state_usd / shock.total_gross_exposure_usd
            self._hl_company_net.set_subtext(f"{net_share:.0%} of gross — Apex pays after resets")
        else:
            self._hl_company_net.set_subtext("")

        self._hl_provider.set_value(
            fmt_usd(shock.total_provider_absorption_steady_state_usd, "M")
        )
        if shock.total_gross_exposure_usd != 0:
            prov_share = (shock.total_provider_absorption_steady_state_usd
                          / shock.total_gross_exposure_usd)
            self._hl_provider.set_subtext(f"{prov_share:.0%} of gross — providers eat indefinitely")
        else:
            self._hl_provider.set_subtext("")

        # Time-phased curve
        weeks = np.array(shock.by_mode_curve.index, dtype=float)
        series_list = []
        for mode in ["air", "ocean", "truck"]:
            if mode in shock.by_mode_curve.columns:
                vals = shock.by_mode_curve[mode].to_numpy().astype(float)
                series_list.append(AreaSeries(
                    label=mode.title(),
                    values=vals,
                    color=theme.MODE_COLORS[mode],
                ))
        # If shock is 0, all series are zero — still show the empty plot
        self._curve.set_data(
            weeks=weeks,
            series_list=series_list,
            first_impact_week=shock.first_company_impact_week,
            steady_state_week=shock.steady_state_week,
        )

        # Lag histogram: aggregate lane-level company_net_steady_state_usd by first_company_impact_week
        lanes = shock.lanes
        within_horizon = lanes[lanes["first_company_impact_week"] <= shock.horizon_weeks]
        if not within_horizon.empty and abs(shock.total_company_net_steady_state_usd) > 0:
            grouped = within_horizon.groupby(
                "first_company_impact_week"
            )["company_net_steady_state_usd"].sum().reindex(
                np.arange(0, shock.horizon_weeks + 1), fill_value=0
            )
            x = grouped.index.to_numpy().astype(float)
            heights = grouped.to_numpy().astype(float)
            self._histogram.set_bars(x, heights)
        else:
            self._histogram.set_bars(np.array([0]), np.array([0]))

        # Concentration callout
        if shock.top_lane_id and abs(shock.top_lane_company_net_usd) > 0:
            top_lane_row = lanes[lanes["lane_id"] == shock.top_lane_id].iloc[0]
            od = f"{top_lane_row['origin_region']}→{top_lane_row['destination_region']}"
            sub = top_lane_row["sub_mode"].replace("_", " ")
            self._top_lane_label.setText("TOP LANE")
            self._top_lane_value.setText(shock.top_lane_id)
            self._top_lane_subtext.setText(
                f"{od} · {sub}<br>"
                f"Company net: <b>{fmt_usd(shock.top_lane_company_net_usd, 'M')}</b>"
            )
            self._top5_value.setText(f"{shock.top_5_lanes_share_of_company_net:.0%}")
        else:
            self._top_lane_label.setText("TOP LANE")
            self._top_lane_value.setText("—")
            self._top_lane_subtext.setText("No company net exposure under this shock")
            self._top5_value.setText("—")

        # Insight box
        self._insight.set_html(self._build_insight_html(shock))

    def _populate_prices_table(self, prices_df: pd.DataFrame):
        rows = []
        for _, r in prices_df.iterrows():
            rows.append([
                r["refined_product"],
                f"{r['elasticity']:.2f}",
                f"${r['baseline_price_usd_per_mt']:,.0f}",
                f"${r['shocked_price_usd_per_mt']:,.0f}",
                f"{r['pct_move']:+.1%}",
            ])
        self._prices_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(val)
                if j > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._prices_table.setItem(i, j, item)
        self._prices_table.resizeColumnsToContents()
        self._prices_table.horizontalHeader().setStretchLastSection(True)

    def _build_insight_html(self, shock) -> str:
        delta = shock.delta_brent_usd_per_bbl
        if delta == 0:
            return (
                "Adjust the <b>Δ Brent</b> slider in the sidebar to simulate a sustained "
                "Brent move. Negative values model conflict de-escalation; positive values "
                "model further geopolitical tension."
            )

        sign = "+" if delta > 0 else ""
        if abs(shock.total_company_net_steady_state_usd) < 1:
            return (
                f"A <b>{sign}${delta:.0f}/bbl</b> Brent shock produces no company net exposure "
                f"within the analysis horizon. The network is fully insulated under this scenario."
            )

        # Top lane info
        lanes = shock.lanes
        top_lane_row = lanes[lanes["lane_id"] == shock.top_lane_id].iloc[0]
        od = f"{top_lane_row['origin_region']}→{top_lane_row['destination_region']}"
        sub = top_lane_row["sub_mode"].replace("_", " ")

        return (
            f"A sustained <b>{sign}${delta:.0f}/bbl</b> Brent shock translates to "
            f"<b>{fmt_usd(shock.total_gross_exposure_usd, 'M')}</b> annual gross fuel exposure "
            f"across the system, of which "
            f"<b>{fmt_usd(shock.total_company_net_steady_state_usd, 'M')}</b> is company net "
            f"(steady-state) and "
            f"<b>{fmt_usd(shock.total_provider_absorption_steady_state_usd, 'M')}</b> is "
            f"absorbed by providers. Largest single-lane impact: <b>{shock.top_lane_id}</b> "
            f"({od}, {sub}) at {fmt_usd(shock.top_lane_company_net_usd, 'M')}. "
            f"First company impact: week <b>{shock.first_company_impact_week}</b>. "
            f"Steady state by week <b>{shock.steady_state_week}</b>."
        )
