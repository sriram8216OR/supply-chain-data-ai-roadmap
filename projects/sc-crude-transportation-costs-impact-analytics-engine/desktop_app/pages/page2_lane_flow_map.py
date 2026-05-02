"""
Page 2 — Lane Flow Map.

Layout (top to bottom):
  - Description line
  - Controls row: vulnerability/shock toggle + filter chips (modes, lane types)
  - Map widget
  - Legend bar (severity gradient swatch + thickness explainer)
  - Top-N flagged lanes table (top 10 by current metric)
  - Auto-generated insight footer
"""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import theme
from ..controller import AppController
from ..widgets.formatting import fmt_usd
from ..widgets.insight_box import InsightBox
from ..widgets.world_flow_map import (
    MapOptions, WorldFlowMap, severity_color,
)


# Visual specs for chips
CHIP_QSS = f"""
QPushButton#chip {{
    background-color: {theme.BG_RAISED};
    color: {theme.TEXT_SECONDARY};
    padding: 5px 12px;
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
QPushButton#layer_toggle {{
    background-color: {theme.BG_RAISED};
    color: {theme.TEXT_SECONDARY};
    padding: 7px 18px;
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


class Page2LaneFlowMap(QWidget):
    def __init__(self, controller: AppController):
        super().__init__()
        self._controller = controller
        self._options = MapOptions()

        # Mode and lane_type chip references
        self._mode_chips: dict[str, QPushButton] = {}
        self._lane_type_chips: dict[str, QPushButton] = {}
        self._layer_buttons: dict[str, QPushButton] = {}
        self._top_only_chip: QPushButton | None = None

        self._build_ui()
        self._populate()

        # Subscribe to shock changes (only refresh when in shock layer mode)
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
            "Geographic visualization of Apex HVAC's freight network. "
            "Switch between <b>vulnerability</b> (structural exposure, shock-independent) "
            "and <b>shock</b> (company net under current Brent shock) layers using the toggle below. "
            "Hover any flow for details."
        )
        desc.setObjectName("section_caption")
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        layout.addWidget(desc)

        # Controls row
        layout.addWidget(self._build_controls())

        # Map panel
        layout.addWidget(self._build_map_panel())

        # Legend
        layout.addWidget(self._build_legend())

        # Top-N table
        layout.addLayout(self._build_top_table_section())

        # Insight box
        self._insight = InsightBox()
        layout.addWidget(self._insight)

        layout.addStretch(1)

    def _build_controls(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setStyleSheet(panel.styleSheet() + CHIP_QSS)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )
        layout.setSpacing(theme.SPACING_SM)

        # Layer toggle row (vulnerability vs shock)
        layer_row = QHBoxLayout()
        layer_row.setSpacing(theme.SPACING_SM)

        layer_label = QLabel("LAYER")
        layer_label.setObjectName("fp_label")
        layer_row.addWidget(layer_label)

        self._layer_group = QButtonGroup(self)
        self._layer_group.setExclusive(True)
        for layer_id, label in [("vulnerability", "Vulnerability"),
                                ("shock", "Shock impact")]:
            btn = QPushButton(label)
            btn.setObjectName("layer_toggle")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _, l=layer_id: self._on_layer_changed(l)
            )
            self._layer_buttons[layer_id] = btn
            self._layer_group.addButton(btn)
            layer_row.addWidget(btn)
        self._layer_buttons["vulnerability"].setChecked(True)

        layer_row.addStretch(1)
        layout.addLayout(layer_row)

        # Filter chips row 1: modes
        modes_row = QHBoxLayout()
        modes_row.setSpacing(theme.SPACING_SM)

        modes_label = QLabel("MODES")
        modes_label.setObjectName("fp_label")
        modes_row.addWidget(modes_label)
        for mode in ["air", "ocean", "truck"]:
            chip = QPushButton(mode.title())
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setChecked(True)
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _, m=mode: self._on_mode_chip_toggled(m))
            self._mode_chips[mode] = chip
            modes_row.addWidget(chip)
        modes_row.addStretch(1)
        layout.addLayout(modes_row)

        # Filter chips row 2: lane types
        lt_row = QHBoxLayout()
        lt_row.setSpacing(theme.SPACING_SM)

        lt_label = QLabel("LANE TYPES")
        lt_label.setObjectName("fp_label")
        lt_row.addWidget(lt_label)

        lt_options = [
            ("inbound_component", "Inbound"),
            ("outbound_finished", "Outbound"),
            ("service_parts", "Service parts"),
        ]
        for lt_id, label in lt_options:
            chip = QPushButton(label)
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setChecked(True)
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(
                lambda _, lt=lt_id: self._on_lane_type_chip_toggled(lt)
            )
            self._lane_type_chips[lt_id] = chip
            lt_row.addWidget(chip)

        # "Top 25%" toggle (separate visually)
        lt_row.addSpacing(theme.SPACING_LG)
        self._top_only_chip = QPushButton("Top 25% only")
        self._top_only_chip.setObjectName("chip")
        self._top_only_chip.setCheckable(True)
        self._top_only_chip.setChecked(False)
        self._top_only_chip.setCursor(Qt.PointingHandCursor)
        self._top_only_chip.clicked.connect(self._on_top_only_toggled)
        lt_row.addWidget(self._top_only_chip)

        lt_row.addStretch(1)
        layout.addLayout(lt_row)

        return panel

    def _build_map_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._map = WorldFlowMap()
        self._map.setMinimumHeight(480)
        layout.addWidget(self._map)

        return panel

    def _build_legend(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_SM,
            theme.SPACING_LG, theme.SPACING_SM,
        )
        layout.setSpacing(theme.SPACING_LG)

        # Severity gradient label
        self._gradient_label = QLabel("LINE COLOR — STRUCTURAL EXPOSURE INTENSITY")
        self._gradient_label.setObjectName("fp_label")
        layout.addWidget(self._gradient_label)

        # Color gradient strip — using a series of small frames
        gradient_frame = QFrame()
        gradient_frame.setFixedHeight(12)
        gradient_frame.setMinimumWidth(160)
        grad_layout = QHBoxLayout(gradient_frame)
        grad_layout.setContentsMargins(0, 0, 0, 0)
        grad_layout.setSpacing(0)
        for i in range(20):
            t = i / 19
            color = severity_color(t)
            cell = QFrame()
            cell.setStyleSheet(f"background-color: {color.name()};")
            cell.setMinimumWidth(8)
            grad_layout.addWidget(cell, 1)

        # Wrap gradient with low/high labels on either side
        gradient_with_labels = QHBoxLayout()
        gradient_with_labels.setSpacing(theme.SPACING_XS)
        gradient_with_labels.addWidget(self._make_tick_label("low"))
        gradient_with_labels.addWidget(gradient_frame, 1)
        gradient_with_labels.addWidget(self._make_tick_label("high"))
        layout.addLayout(gradient_with_labels)

        layout.addStretch(1)
        layout.addWidget(self._make_tick_label("LINE THICKNESS — ANNUAL TRANSPORT COST"))
        layout.addWidget(self._make_thickness_demo())

        return panel

    def _make_tick_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{theme.TEXT_MUTED}; font-size:{theme.FONT_SIZE_TINY}px; "
            f"text-transform:uppercase; letter-spacing:0.05em;"
        )
        return lbl

    def _make_thickness_demo(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumWidth(120)
        frame.setMinimumHeight(20)
        # We'd ideally paint a thin→thick line; for simplicity, three tick labels
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(theme.SPACING_SM)
        for label, w in [("$1M", 1), ("$10M", 3), ("$50M+", 5)]:
            cell = QFrame()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(2)
            line = QFrame()
            line.setFixedHeight(w)
            line.setStyleSheet(f"background:{theme.TEXT_SECONDARY};")
            cell_layout.addWidget(line)
            tick = self._make_tick_label(label)
            cell_layout.addWidget(tick)
            layout.addWidget(cell)
        return frame

    def _build_top_table_section(self) -> QVBoxLayout:
        wrap = QVBoxLayout()
        wrap.setSpacing(theme.SPACING_SM)

        heading = QLabel("Top flagged lanes")
        heading.setObjectName("section_heading")
        wrap.addWidget(heading)

        self._top_caption = QLabel("Top 10 lanes by structural exposure (current filter).")
        self._top_caption.setObjectName("section_caption")
        wrap.addWidget(self._top_caption)

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_MD,
            theme.SPACING_LG, theme.SPACING_MD,
        )

        self._top_table = QTableWidget(10, 6)
        self._top_table.setHorizontalHeaderLabels(
            ["Lane ID", "O→D", "Sub-mode", "Type", "Annual cost", "Metric"]
        )
        self._top_table.verticalHeader().setVisible(False)
        self._top_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._top_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._top_table.setSelectionMode(QTableWidget.SingleSelection)
        self._top_table.setShowGrid(False)
        self._top_table.setAlternatingRowColors(False)
        self._top_table.setStyleSheet(f"""
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
        """)
        self._top_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._top_table.horizontalHeader().setStretchLastSection(True)
        self._top_table.setFixedHeight(280)
        panel_layout.addWidget(self._top_table)
        wrap.addWidget(panel)
        return wrap

    # -------------------------------------------------------------------
    # Event handlers
    # -------------------------------------------------------------------

    def _on_layer_changed(self, layer: str):
        self._options.layer = layer
        self._refresh_legend_label()
        self._populate()

    def _on_mode_chip_toggled(self, mode: str):
        if self._mode_chips[mode].isChecked():
            self._options.modes_enabled.add(mode)
        else:
            self._options.modes_enabled.discard(mode)
        self._populate()

    def _on_lane_type_chip_toggled(self, lt: str):
        if self._lane_type_chips[lt].isChecked():
            self._options.lane_types_enabled.add(lt)
        else:
            self._options.lane_types_enabled.discard(lt)
        self._populate()

    def _on_top_only_toggled(self):
        self._options.show_top_only = self._top_only_chip.isChecked()
        self._populate()

    def _on_shock_changed(self, shock_result):
        if self._options.layer == "shock":
            self._map.set_shock_result(shock_result)
            self._populate_table()
            self._populate_insight()

    # -------------------------------------------------------------------
    # Data population
    # -------------------------------------------------------------------

    def _refresh_legend_label(self):
        if self._options.layer == "vulnerability":
            self._gradient_label.setText("LINE COLOR — STRUCTURAL EXPOSURE INTENSITY")
            self._top_caption.setText("Top 10 lanes by structural exposure (current filter).")
        else:
            self._gradient_label.setText("LINE COLOR — COMPANY NET EXPOSURE INTENSITY")
            delta = self._controller.delta_brent
            sign = "+" if delta >= 0 else ""
            self._top_caption.setText(
                f"Top 10 lanes by company net under {sign}${delta:.0f}/bbl Brent shock "
                "(current filter)."
            )

    def _populate(self):
        self._map.set_data(
            diagnostic=self._controller.diagnostic,
            shock_result=self._controller.shock_result,
            region_anchors=self._controller.network.region_anchors,
            options=self._options,
        )
        self._populate_table()
        self._populate_insight()

    def _populate_table(self):
        rows = self._map.get_filtered_lanes()[:10]
        self._top_table.setRowCount(max(1, len(rows)))
        if not rows:
            placeholder = QTableWidgetItem("No lanes match current filters")
            placeholder.setTextAlignment(Qt.AlignCenter)
            self._top_table.setItem(0, 0, placeholder)
            self._top_table.setSpan(0, 0, 1, 6)
            return
        self._top_table.clearSpans()
        for i, row in enumerate(rows):
            cells = [
                row["lane_id"],
                row["od"],
                row["sub_mode"].replace("_", " "),
                row["lane_type"].replace("_", " "),
                fmt_usd(row["annual_cost"], "M"),
                fmt_usd(row["metric_value"], "M"),
            ]
            for j, val in enumerate(cells):
                item = QTableWidgetItem(val)
                if j >= 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self._top_table.setItem(i, j, item)

    def _populate_insight(self):
        rows = self._map.get_filtered_lanes()
        if not rows:
            self._insight.set_html(
                "No lanes match the current filter selection. Toggle modes or lane types to see flows."
            )
            return

        # Aggregate by region for insight
        from collections import defaultdict
        by_origin = defaultdict(float)
        by_destination = defaultdict(float)
        for r in rows:
            o, d = r["od"].split("→")
            by_origin[o] += abs(r["metric_value"])
            by_destination[d] += abs(r["metric_value"])

        top_origin = max(by_origin.items(), key=lambda x: x[1])[0]
        top_dest = max(by_destination.items(), key=lambda x: x[1])[0]
        top_lane = rows[0]
        n_lanes = len(rows)
        total_metric = sum(abs(r["metric_value"]) for r in rows)

        if self._options.layer == "vulnerability":
            metric_word = "structural exposure"
        else:
            metric_word = "company net exposure"

        sentence = (
            f"Across <b>{n_lanes}</b> filtered inter-region lanes, total {metric_word} is "
            f"<b>{fmt_usd(total_metric, 'M')}</b>. Largest origin: <b>{top_origin}</b>; "
            f"largest destination: <b>{top_dest}</b>. Top lane: <b>{top_lane['lane_id']}</b> "
            f"({top_lane['od']}, {top_lane['sub_mode'].replace('_', ' ')}) at "
            f"<b>{fmt_usd(top_lane['metric_value'], 'M')}</b>."
        )
        self._insight.set_html(sentence)
