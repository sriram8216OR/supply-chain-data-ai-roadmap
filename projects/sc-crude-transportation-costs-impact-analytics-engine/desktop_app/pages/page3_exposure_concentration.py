"""
Page 3 — Exposure Concentration.

Strategic question: where exactly is exposure concentrated, and is that
concentration something to worry about?

Layout (top to bottom):
  - Description
  - Headline strip: 3 concentration metrics (top-5 share, top-10 share, lanes-to-80%)
  - Pareto curve (full width) with vulnerability/shock layer toggle
  - Lane-type × contract-archetype matrix: shows insulation profile per lane type
  - Provider concentration: top providers by exposure share
  - Top-15 lanes table
  - Auto insight footer
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import theme
from ..controller import AppController
from ..widgets.formatting import fmt_usd
from ..widgets.headline_number import HeadlineNumber
from ..widgets.insight_box import InsightBox
from ..widgets.pareto_curve import ParetoCurve
from ..widgets.stacked_bar import StackedBar


# Visual specs reused
LAYER_QSS = f"""
QPushButton#layer_toggle {{
    background-color: {theme.BG_RAISED};
    color: {theme.TEXT_SECONDARY};
    padding: 6px 16px;
    border: 1px solid {theme.BORDER_SUBTLE};
    border-radius: 4px;
    font-size: {theme.FONT_SIZE_BASE}px;
    font-weight: 500;
}}
QPushButton#layer_toggle:hover {{
    color: {theme.TEXT_PRIMARY};
    border-color: {theme.BORDER_STRONG};
}}
QPushButton#layer_toggle:checked {{
    background-color: {theme.ACCENT_PRIMARY};
    color: white;
    border-color: {theme.ACCENT_PRIMARY};
}}
"""


class Page3ExposureConcentration(QWidget):
    def __init__(self, controller: AppController):
        super().__init__()
        self._controller = controller
        self._layer = "vulnerability"  # "vulnerability" | "shock"
        self._layer_buttons: dict[str, QPushButton] = {}

        self._build_ui()
        self._populate()

        # Subscribe to shock changes (refresh only if shock layer active)
        self._controller.shock_changed.connect(self._on_shock_changed)

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

        # Description
        desc = QLabel(
            "Where is exposure concentrated? A network with 5 lanes carrying "
            "80% of exposure is qualitatively different — and easier to act on — than one "
            "with the same total spread across 50 lanes. Toggle layers to compare structural "
            "concentration vs. shock-driven concentration."
        )
        desc.setObjectName("section_caption")
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        layout.addWidget(desc)

        # Layer toggle row
        layout.addWidget(self._build_layer_toggle())

        # Headline strip
        layout.addWidget(self._build_headline_strip())

        # Pareto curve
        layout.addLayout(self._build_pareto_section())

        # Lane-type × archetype matrix
        layout.addLayout(self._build_archetype_matrix_section())

        # Provider concentration
        layout.addLayout(self._build_provider_section())

        # Top-15 lanes table
        layout.addLayout(self._build_top_table_section())

        # Insight footer
        self._insight = InsightBox()
        layout.addWidget(self._insight)

        layout.addStretch(1)

    def _build_layer_toggle(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet(panel.styleSheet() + LAYER_QSS)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_SM,
            theme.SPACING_LG, theme.SPACING_SM,
        )
        layout.setSpacing(theme.SPACING_SM)

        label = QLabel("LAYER")
        label.setObjectName("fp_label")
        layout.addWidget(label)

        self._layer_group = QButtonGroup(self)
        self._layer_group.setExclusive(True)
        for layer_id, lbl in [("vulnerability", "Vulnerability"),
                              ("shock", "Shock impact")]:
            btn = QPushButton(lbl)
            btn.setObjectName("layer_toggle")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, l=layer_id: self._on_layer_changed(l))
            self._layer_buttons[layer_id] = btn
            self._layer_group.addButton(btn)
            layout.addWidget(btn)
        self._layer_buttons["vulnerability"].setChecked(True)

        layout.addStretch(1)
        return panel

    def _build_headline_strip(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.SPACING_MD)

        self._hl_top5 = HeadlineNumber("Top 5 Lanes Share")
        self._hl_top10 = HeadlineNumber("Top 10 Lanes Share")
        self._hl_to80 = HeadlineNumber("Lanes to Reach 80%")

        row.addWidget(self._hl_top5, 1)
        row.addWidget(self._hl_top10, 1)
        row.addWidget(self._hl_to80, 1)
        return wrap

    def _build_pareto_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Pareto curve — cumulative concentration by lane rank")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        self._pareto_caption = QLabel()
        self._pareto_caption.setObjectName("section_caption")
        self._pareto_caption.setWordWrap(True)
        wrap.addWidget(self._pareto_caption)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_SM, theme.SPACING_SM,
            theme.SPACING_SM, theme.SPACING_SM,
        )
        self._pareto = ParetoCurve()
        panel_layout.addWidget(self._pareto)
        wrap.addWidget(panel)

        return wrap

    def _build_archetype_matrix_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Contract archetype mix by lane type")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        caption = QLabel(
            "Volume-weighted distribution of contract archetypes within each lane type. "
            "Indicates how production-critical (inbound), volume-driven (outbound), "
            "urgency-driven (service parts), and last-mile (intra-region) flows differ "
            "in their insulation profile."
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
        panel_layout.setSpacing(theme.SPACING_SM)

        # Container of stacked bars, one per lane type
        self._archetype_bars: dict[str, StackedBar] = {}
        self._archetype_pt_labels: dict[str, QLabel] = {}

        for lt_key, lt_label in [
            ("inbound_component", "Inbound component"),
            ("outbound_finished", "Outbound finished"),
            ("service_parts", "Service parts"),
            ("intra_region_distribution", "Intra-region distribution"),
        ]:
            row_widget = QFrame()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(theme.SPACING_MD)

            # Label column (fixed width for alignment)
            label = QLabel(lt_label)
            label.setStyleSheet(
                f"color:{theme.TEXT_PRIMARY}; "
                f"font-size:{theme.FONT_SIZE_SMALL}px; "
                f"font-weight:500;"
            )
            label.setMinimumWidth(180)
            label.setMaximumWidth(180)
            row_layout.addWidget(label)

            # Stacked bar
            bar = StackedBar()
            self._archetype_bars[lt_key] = bar
            row_layout.addWidget(bar, 1)

            # Blended pass-through readout
            pt_label = QLabel("—")
            pt_label.setStyleSheet(
                f"color:{theme.TEXT_SECONDARY}; "
                f"font-family:{theme.FONT_FAMILY_MONO}; "
                f"font-size:{theme.FONT_SIZE_SMALL}px;"
            )
            pt_label.setMinimumWidth(140)
            pt_label.setMaximumWidth(140)
            pt_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._archetype_pt_labels[lt_key] = pt_label
            row_layout.addWidget(pt_label)

            panel_layout.addWidget(row_widget)

        wrap.addWidget(panel)
        return wrap

    def _build_provider_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Provider concentration")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        self._provider_caption = QLabel()
        self._provider_caption.setObjectName("section_caption")
        self._provider_caption.setWordWrap(True)
        wrap.addWidget(self._provider_caption)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )

        self._provider_table = QTableWidget(10, 4)
        self._provider_table.setHorizontalHeaderLabels(
            ["Provider", "Lanes served", "Volume share", "Exposure share"]
        )
        self._provider_table.verticalHeader().setVisible(False)
        self._provider_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._provider_table.setSelectionMode(QTableWidget.NoSelection)
        self._provider_table.setShowGrid(False)
        self._provider_table.setStyleSheet(self._table_qss())
        self._provider_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._provider_table.horizontalHeader().setStretchLastSection(True)
        self._provider_table.setFixedHeight(280)
        panel_layout.addWidget(self._provider_table)
        wrap.addWidget(panel)
        return wrap

    def _build_top_table_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Top 15 lanes by exposure")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        self._top_caption = QLabel()
        self._top_caption.setObjectName("section_caption")
        wrap.addWidget(self._top_caption)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )

        self._top_table = QTableWidget(15, 7)
        self._top_table.setHorizontalHeaderLabels(
            ["Rank", "Lane", "O→D", "Sub-mode", "Type", "Metric", "Cumulative %"]
        )
        self._top_table.verticalHeader().setVisible(False)
        self._top_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._top_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._top_table.setSelectionMode(QTableWidget.SingleSelection)
        self._top_table.setShowGrid(False)
        self._top_table.setStyleSheet(self._table_qss())
        self._top_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._top_table.horizontalHeader().setStretchLastSection(True)
        self._top_table.setFixedHeight(380)
        panel_layout.addWidget(self._top_table)
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

    def _on_layer_changed(self, layer: str):
        self._layer = layer
        self._populate()

    def _on_shock_changed(self, shock_result):
        if self._layer == "shock":
            self._populate()

    # -------------------------------------------------------------------
    # Data population
    # -------------------------------------------------------------------

    def _get_metric_data(self) -> tuple[pd.DataFrame, str, str]:
        """Return (lanes_df_with_metric, metric_label, metric_word).

        lanes_df has columns: lane_id, origin_region, destination_region,
            sub_mode, lane_type, mode, annual_transportation_cost_usd, metric_value
        Always sorted descending by absolute metric value.
        """
        diag = self._controller.diagnostic
        lanes = diag.lanes.copy()

        if self._layer == "vulnerability":
            lanes["metric_value"] = lanes["structural_exposure_usd"]
            metric_label = "Structural exposure"
            metric_word = "structural exposure"
        else:
            shock = self._controller.shock_result
            shock_lanes = shock.lanes.set_index("lane_id")
            lanes = lanes.set_index("lane_id")
            lanes["metric_value"] = shock_lanes["company_net_steady_state_usd"]
            lanes = lanes.reset_index()
            metric_label = "Company net (steady-state)"
            metric_word = "company net exposure"

        # Sort descending by absolute value
        lanes = lanes.assign(_abs=lanes["metric_value"].abs())
        lanes = lanes.sort_values("_abs", ascending=False).drop(columns="_abs").reset_index(drop=True)
        return lanes, metric_label, metric_word

    def _populate(self):
        lanes, metric_label, metric_word = self._get_metric_data()
        total_metric = float(lanes["metric_value"].abs().sum())

        # ---- Pareto data ----
        n = len(lanes)
        cum_abs = lanes["metric_value"].abs().cumsum().values
        cumulative_pct = (cum_abs / total_metric * 100) if total_metric > 0 else np.zeros(n)
        ranks = np.arange(1, n + 1)

        # Headline strip
        top5_pct = float(cumulative_pct[4]) if n >= 5 else float(cumulative_pct[-1] if n else 0)
        top10_pct = float(cumulative_pct[9]) if n >= 10 else float(cumulative_pct[-1] if n else 0)
        # Lanes needed to reach 80%
        if total_metric > 0:
            lanes_to_80 = int(np.searchsorted(cumulative_pct, 80) + 1)
            lanes_to_80 = min(lanes_to_80, n)
        else:
            lanes_to_80 = 0

        self._hl_top5.set_value(f"{top5_pct:.0f}%")
        self._hl_top5.set_subtext(f"of {metric_word}")
        self._hl_top10.set_value(f"{top10_pct:.0f}%")
        self._hl_top10.set_subtext(f"of {metric_word}")
        self._hl_to80.set_value(str(lanes_to_80))
        self._hl_to80.set_subtext(f"out of {n} lanes ({lanes_to_80 / max(n, 1):.0%} of network)")

        # Pareto caption
        if self._layer == "vulnerability":
            self._pareto_caption.setText(
                "Lanes ranked by structural exposure $, with cumulative % of network total. "
                "A steeper curve means more concentration; a flatter curve means broader distribution."
            )
        else:
            delta = self._controller.delta_brent
            sign = "+" if delta >= 0 else ""
            self._pareto_caption.setText(
                f"Lanes ranked by company net under {sign}${delta:.0f}/bbl Brent shock, "
                "with cumulative % of company net total."
            )

        self._pareto.set_data(
            ranks=ranks.astype(float),
            cumulative_pct=cumulative_pct,
            marker_ranks=[5, 10, 25] if n >= 25 else [5, 10, n // 2],
        )

        # ---- Archetype matrix ----
        self._populate_archetype_matrix()

        # ---- Provider concentration ----
        self._populate_provider_table(lanes, total_metric, metric_label, metric_word)

        # ---- Top-15 table ----
        self._populate_top_table(lanes, cumulative_pct, metric_label)

        # ---- Insight footer ----
        self._populate_insight(lanes, top5_pct, top10_pct, lanes_to_80, n,
                               total_metric, metric_word)

    def _populate_archetype_matrix(self):
        """Per lane_type, show stacked bar of archetype shares + blended pass-through."""
        contracts = self._controller.network.lane_contracts
        archetypes = self._controller.network.contract_archetypes
        diag_lanes = self._controller.diagnostic.lanes

        # Compute volume-weighted archetype share per lane_type
        contracts = contracts.merge(
            diag_lanes[["lane_id", "lane_type", "annual_volume_tons"]],
            on="lane_id",
        )
        contracts["weighted_volume"] = (
            contracts["share_of_lane_volume"] * contracts["annual_volume_tons"]
        )
        contracts = contracts.merge(
            archetypes, left_on="contract_archetype", right_on="archetype"
        )
        contracts["pt_x_volume"] = contracts["pass_through_pct"] * contracts["weighted_volume"]

        archetype_order = ["spot", "indexed_short", "indexed_medium", "baf_long", "fixed"]

        for lt_key, bar in self._archetype_bars.items():
            lt_subset = contracts[contracts["lane_type"] == lt_key]
            total_vol = float(lt_subset["weighted_volume"].sum())
            if total_vol <= 0:
                bar.set_segments([])
                self._archetype_pt_labels[lt_key].setText("no lanes")
                continue
            segments = []
            for arch in archetype_order:
                vol = float(lt_subset[lt_subset["contract_archetype"] == arch]["weighted_volume"].sum())
                if vol > 0:
                    segments.append((
                        arch.replace("_", " "),
                        vol,
                        theme.ARCHETYPE_COLORS[arch],
                    ))
            bar.set_segments(segments)

            blended_pt = float(lt_subset["pt_x_volume"].sum() / total_vol)
            self._archetype_pt_labels[lt_key].setText(f"PT {blended_pt:.0%}")

    def _populate_provider_table(self, lanes_df: pd.DataFrame, total_metric: float,
                                  metric_label: str, metric_word: str):
        """Compute exposure share per provider, show top 10."""
        contracts = self._controller.network.lane_contracts.copy()
        # Each contract row contributes share_of_lane_volume * lane_metric_value to provider's exposure share
        lane_metric = dict(zip(lanes_df["lane_id"], lanes_df["metric_value"]))
        lane_volume = dict(zip(lanes_df["lane_id"], lanes_df["annual_volume_tons"]))

        contracts["lane_metric"] = contracts["lane_id"].map(lane_metric)
        contracts["lane_volume"] = contracts["lane_id"].map(lane_volume)
        contracts["provider_metric"] = (
            contracts["share_of_lane_volume"] * contracts["lane_metric"].abs()
        )
        contracts["provider_volume"] = (
            contracts["share_of_lane_volume"] * contracts["lane_volume"]
        )

        per_provider = contracts.groupby("provider_name").agg(
            lanes_served=("lane_id", "nunique"),
            volume=("provider_volume", "sum"),
            metric_exposure=("provider_metric", "sum"),
        ).reset_index()

        total_volume = float(per_provider["volume"].sum())
        per_provider["volume_share"] = per_provider["volume"] / max(total_volume, 1)
        per_provider["metric_share"] = per_provider["metric_exposure"] / max(total_metric, 1)
        per_provider = per_provider.sort_values("metric_share", ascending=False).head(10)

        # Caption
        top_provider = per_provider.iloc[0]
        top_provider_share = float(top_provider["metric_share"])
        top3_share = float(per_provider.head(3)["metric_share"].sum())
        self._provider_caption.setText(
            f"Top provider carries <b>{top_provider_share:.0%}</b> of {metric_word}; "
            f"top 3 providers account for <b>{top3_share:.0%}</b>. "
            "Higher concentration means greater dependence on a single counterparty."
        )
        self._provider_caption.setTextFormat(Qt.RichText)

        # Populate table
        self._provider_table.setRowCount(len(per_provider))
        for i, (_, row) in enumerate(per_provider.iterrows()):
            cells = [
                row["provider_name"],
                str(int(row["lanes_served"])),
                f"{row['volume_share']:.1%}",
                f"{row['metric_share']:.1%}",
            ]
            for j, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if j == 0:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._provider_table.setItem(i, j, item)

    def _populate_top_table(self, lanes_df: pd.DataFrame, cumulative_pct: np.ndarray,
                            metric_label: str):
        top = lanes_df.head(15)
        n = len(top)
        if self._layer == "vulnerability":
            self._top_caption.setText("Ranked by structural exposure (descending).")
        else:
            delta = self._controller.delta_brent
            sign = "+" if delta >= 0 else ""
            self._top_caption.setText(
                f"Ranked by company net under {sign}${delta:.0f}/bbl Brent shock (descending)."
            )

        self._top_table.setRowCount(n)
        for i, (_, row) in enumerate(top.iterrows()):
            cum = float(cumulative_pct[i])
            cells = [
                str(i + 1),
                row["lane_id"],
                f"{row['origin_region']}→{row['destination_region']}",
                row["sub_mode"].replace("_", " "),
                row["lane_type"].replace("_", " "),
                fmt_usd(float(row["metric_value"]), "M"),
                f"{cum:.1f}%",
            ]
            for j, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if j in (0, 5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._top_table.setItem(i, j, item)

    def _populate_insight(self, lanes_df: pd.DataFrame, top5_pct: float, top10_pct: float,
                          lanes_to_80: int, n: int, total_metric: float, metric_word: str):
        if total_metric <= 0:
            self._insight.set_html(
                "No exposure under current selection."
            )
            return

        # Mode concentration of top 10
        top10 = lanes_df.head(10)
        mode_in_top10 = top10["mode"].value_counts()
        dominant_mode_top10 = mode_in_top10.idxmax()
        dominant_mode_count = int(mode_in_top10.iloc[0])

        lane_type_in_top10 = top10["lane_type"].value_counts()
        dominant_lt_top10 = lane_type_in_top10.idxmax()
        dominant_lt_count = int(lane_type_in_top10.iloc[0])

        sentence = (
            f"Top <b>5</b> lanes carry <b>{top5_pct:.0f}%</b> and top <b>10</b> carry "
            f"<b>{top10_pct:.0f}%</b> of {metric_word}. To cover 80% of exposure requires "
            f"<b>{lanes_to_80}</b> lanes ({lanes_to_80 / n:.0%} of the network). "
            f"In the top 10, <b>{dominant_mode_count}/10</b> are {dominant_mode_top10} and "
            f"<b>{dominant_lt_count}/10</b> are {dominant_lt_top10.replace('_', ' ')} flows."
        )
        self._insight.set_html(sentence)
