"""
Main window — QMainWindow with sidebar (nav + shock selector) + content area.

Layout:
  +-----------------+--------------------------------+
  |                 |  Page header (title/subtitle)  |
  |   Sidebar       +--------------------------------+
  |   - app title   |                                |
  |   - nav (7)     |   Content (QStackedWidget)     |
  |   - shock       |                                |
  |     selector    |                                |
  |                 |                                |
  |                 |                                |
  +-----------------+--------------------------------+
  |                 Status bar                       |
  +--------------------------------------------------+
"""

from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QSlider, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from . import theme
from .controller import AppController


# ---------------------------------------------------------------------------
# Page registry — central definition of all pages
# ---------------------------------------------------------------------------

# Each page is registered with: id, label (sidebar), title (page header), subtitle,
# and a factory function that takes the controller and returns the page widget.
# Pages 2-7 have placeholders for now; we add real implementations later.

PAGES = []  # populated in _register_pages()


def _register_pages():
    """Lazy import to avoid circular imports."""
    global PAGES
    from .pages.page1_executive import Page1ExecutiveSummary
    from .pages.page2_lane_flow_map import Page2LaneFlowMap
    from .pages.page3_exposure_concentration import Page3ExposureConcentration
    from .pages.page4_time_phased_impact import Page4TimePhasedImpact
    from .pages.placeholder import PlaceholderPage

    PAGES = [
        ("page1", "📊  Executive Summary",
         "Executive Summary",
         "Network vulnerability snapshot and shock impact simulator",
         Page1ExecutiveSummary),
        ("page2", "🌍  Lane Flow Map",
         "Lane Flow Map",
         "Geographic visualization of network flows with vulnerability/shock overlays",
         Page2LaneFlowMap),
        ("page3", "📈  Exposure Concentration",
         "Exposure Concentration",
         "Pareto views and breakdowns by lane, mode, lane type, and contract archetype",
         Page3ExposureConcentration),
        ("page4", "⏱️  Time-Phased Impact",
         "Time-Phased Impact",
         "Detailed staircase analysis under shock — by lane, mode, lane type, archetype",
         Page4TimePhasedImpact),
        ("page5", "🔁  Pass-Through Reality",
         "Pass-Through Reality Check",
         "Gross vs net waterfall and insulation analysis across the network",
         lambda ctl: PlaceholderPage("Pass-Through Reality Check", "Coming soon")),
        ("page6", "🚢  Mode Comparison",
         "Mode Comparison",
         "Network-design lens with cost-per-ton-km and mode-shift breakeven",
         lambda ctl: PlaceholderPage("Mode Comparison", "Coming soon")),
        ("page7", "🧪  Scenario Library",
         "Scenario Library",
         "Predefined scenarios and what-if comparisons",
         lambda ctl: PlaceholderPage("Scenario Library", "Coming soon")),
    ]


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, controller: AppController):
        super().__init__()
        self._controller = controller
        _register_pages()

        self.setWindowTitle("Apex HVAC — Crude Exposure Intelligence")
        self.resize(theme.WINDOW_INITIAL_WIDTH, theme.WINDOW_INITIAL_HEIGHT)

        self._page_widgets: dict[str, QWidget] = {}
        self._page_titles: dict[str, tuple[str, str]] = {}
        self._build_ui()
        self._connect_signals()
        self._select_page("page1")

    # -------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------

    def _build_ui(self):
        # Central widget: horizontal split of sidebar + content
        central = QWidget()
        central.setObjectName("central")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = self._build_sidebar()
        content = self._build_content_area()

        root.addWidget(sidebar)
        root.addWidget(content, stretch=1)

        self.setCentralWidget(central)
        self._build_status_bar()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(theme.SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(
            theme.SPACING_LG, theme.SPACING_LG,
            theme.SPACING_LG, theme.SPACING_LG,
        )
        layout.setSpacing(theme.SPACING_SM)

        # App title
        title = QLabel("Apex HVAC Global")
        title.setObjectName("sidebar_app_title")
        layout.addWidget(title)

        subtitle = QLabel("CRUDE EXPOSURE INTELLIGENCE")
        subtitle.setObjectName("sidebar_app_subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(theme.SPACING_LG)

        # Navigation
        nav_label = QLabel("Pages")
        nav_label.setObjectName("sidebar_section_label")
        layout.addWidget(nav_label)

        self._nav_button_group = QButtonGroup(self)
        self._nav_button_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}

        for page_id, label, _, _, _ in PAGES:
            btn = QPushButton(label)
            btn.setObjectName("sidebar_nav_button")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, pid=page_id: self._select_page(pid))
            self._nav_button_group.addButton(btn)
            self._nav_buttons[page_id] = btn
            layout.addWidget(btn)

        # Push shock selector to the bottom
        layout.addStretch(1)

        # Shock selector section
        shock_label = QLabel("Global Shock")
        shock_label.setObjectName("sidebar_section_label")
        layout.addWidget(shock_label)

        # Baseline reference text
        baseline_text = QLabel(
            f"Baseline: ${self._controller.baseline_brent:.0f}/bbl Brent\n"
            "(April 2026, war-elevated)"
        )
        baseline_text.setObjectName("headline_subtext")
        baseline_text.setWordWrap(True)
        layout.addWidget(baseline_text)

        # Slider value display
        self._shock_value_label = QLabel()
        self._shock_value_label.setObjectName("headline_value")
        self._shock_value_label.setStyleSheet(
            f"font-size: {theme.FONT_SIZE_HEADING + 2}px; "
            f"color: {theme.TEXT_PRIMARY};"
        )
        self._shock_value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._shock_value_label)

        # The slider
        self._shock_slider = QSlider(Qt.Horizontal)
        self._shock_slider.setMinimum(-30)
        self._shock_slider.setMaximum(50)
        self._shock_slider.setSingleStep(1)
        self._shock_slider.setPageStep(5)
        self._shock_slider.setValue(int(self._controller.delta_brent))
        layout.addWidget(self._shock_slider)

        # Shocked Brent display
        self._shocked_brent_label = QLabel()
        self._shocked_brent_label.setObjectName("headline_subtext")
        self._shocked_brent_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._shocked_brent_label)

        # Preset buttons grid (2x2)
        preset_grid = QFrame()
        preset_layout = QVBoxLayout(preset_grid)
        preset_layout.setContentsMargins(0, theme.SPACING_SM, 0, 0)
        preset_layout.setSpacing(theme.SPACING_XS)

        row1 = QHBoxLayout()
        row1.setSpacing(theme.SPACING_XS)
        row2 = QHBoxLayout()
        row2.setSpacing(theme.SPACING_XS)

        presets = [
            ("Hormuz +$40", 40.0, row1),
            ("Tension +$15", 15.0, row1),
            ("Ceasefire -$15", -15.0, row2),
            ("Reset 0", 0.0, row2),
        ]
        for text, value, target_row in presets:
            btn = QPushButton(text)
            btn.setObjectName("preset_button")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, v=value: self._on_preset_clicked(v))
            target_row.addWidget(btn)
        preset_layout.addLayout(row1)
        preset_layout.addLayout(row2)
        layout.addWidget(preset_grid)

        self._update_shock_displays(self._controller.delta_brent)

        return sidebar

    def _build_content_area(self) -> QFrame:
        content = QFrame()
        content.setObjectName("content_area")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Page header
        header = QFrame()
        header.setObjectName("page_header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(
            theme.SPACING_XL, theme.SPACING_LG,
            theme.SPACING_XL, theme.SPACING_LG,
        )
        header_layout.setSpacing(theme.SPACING_XS)

        self._page_title_label = QLabel()
        self._page_title_label.setObjectName("page_title")
        header_layout.addWidget(self._page_title_label)

        self._page_subtitle_label = QLabel()
        self._page_subtitle_label.setObjectName("page_subtitle")
        header_layout.addWidget(self._page_subtitle_label)

        layout.addWidget(header)

        # Stacked content: one widget per page
        self._stack = QStackedWidget()
        for page_id, _, _, _, factory in PAGES:
            page = factory(self._controller)
            self._page_widgets[page_id] = page
            self._stack.addWidget(page)

        layout.addWidget(self._stack, stretch=1)

        return content

    def _build_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)

        n_lanes = self._controller.network.n_lanes
        n_contracts = self._controller.network.n_contracts
        n_warnings = len(self._controller.network.warnings)
        warning_text = "✓ Validated" if n_warnings == 0 else f"⚠ {n_warnings} warnings"

        status_msg = (
            f"  {warning_text}  ·  "
            f"{n_lanes} lanes  ·  {n_contracts} contracts  ·  "
            f"Network total: ${self._controller.diagnostic.total_annual_transportation_cost_usd / 1e9:.2f}B  ·  "
            f"Methodology v3 (Apex HVAC)"
        )
        status.showMessage(status_msg)

    # -------------------------------------------------------------------
    # Signals & navigation
    # -------------------------------------------------------------------

    def _connect_signals(self):
        # Slider -> controller
        self._shock_slider.valueChanged.connect(self._on_slider_changed)
        # Controller's intermediate signal -> slider sync (when preset clicked)
        self._controller.shock_value_changed.connect(self._on_shock_value_changed)

    def _on_slider_changed(self, value: int):
        self._controller.set_delta_brent(float(value))

    def _on_preset_clicked(self, value: float):
        # Set slider; valueChanged will fire if value differs, which propagates
        # to the controller.
        self._shock_slider.setValue(int(value))

    def _on_shock_value_changed(self, value: float):
        # Reflect the new value in the sidebar display immediately (without
        # waiting for the debounced compute). Also keep the slider in sync if
        # something other than the slider triggered the change.
        self._update_shock_displays(value)
        if int(self._shock_slider.value()) != int(value):
            blocker = self._shock_slider.blockSignals(True)
            self._shock_slider.setValue(int(value))
            self._shock_slider.blockSignals(blocker)

    def _update_shock_displays(self, value: float):
        sign = "+" if value > 0 else ""
        self._shock_value_label.setText(f"{sign}${value:.0f}/bbl")

        new_brent = self._controller.baseline_brent + value
        pct = value / self._controller.baseline_brent * 100
        pct_sign = "+" if pct >= 0 else ""
        self._shocked_brent_label.setText(
            f"Shocked: ${new_brent:.0f}/bbl ({pct_sign}{pct:.1f}%)"
        )

    def _select_page(self, page_id: str):
        # Find the index of the page
        for i, (pid, _, title, subtitle, _) in enumerate(PAGES):
            if pid == page_id:
                self._stack.setCurrentIndex(i)
                self._page_title_label.setText(title)
                self._page_subtitle_label.setText(subtitle)
                btn = self._nav_buttons[pid]
                if not btn.isChecked():
                    btn.setChecked(True)
                break
