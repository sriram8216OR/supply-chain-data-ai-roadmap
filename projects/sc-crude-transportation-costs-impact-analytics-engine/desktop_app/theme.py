"""
Theme — central design system for the Apex HVAC Crude Exposure desktop app.

Bloomberg-terminal-inspired dark theme:
  - Dense information layout
  - Monospace numbers for tabular/metric values
  - Severity-coded accent colors (red = high exposure, green = insulated)
  - Subtle dividers and borders for panel separation
  - Generous use of muted text for labels/metadata

All colors and fonts referenced by other modules should come from here, so the
visual system is changeable from one place.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

# Background tiers (darkest to lightest)
BG_DEEP = "#0E0F12"       # darkest — main window background
BG_BASE = "#15171C"       # standard panel background
BG_RAISED = "#1C1F26"     # raised cards / hover states
BG_HIGHLIGHT = "#252934"  # active selections, hover

# Borders and dividers
BORDER_SUBTLE = "#2A2D36"
BORDER_STRONG = "#3A3F4B"

# Text tiers (brightest to dimmest)
TEXT_PRIMARY = "#E8E9ED"
TEXT_SECONDARY = "#A8ACB8"
TEXT_MUTED = "#6B6F7A"
TEXT_LABEL = "#8A8E99"  # for small uppercase labels

# Accent / brand
ACCENT_PRIMARY = "#5B8DEF"  # primary blue — selection, focus, links
ACCENT_HOVER = "#7BA5F4"

# Severity colors (used for exposure severity, mode classification)
SEV_HIGH = "#E94B5C"        # red — high exposure / spot-like
SEV_MED_HIGH = "#F0964D"    # orange
SEV_MED = "#F2C14E"         # yellow
SEV_MED_LOW = "#87B47C"     # light green
SEV_LOW = "#4A8B6F"         # green — insulated / fixed-like

# Mode colors (consistent with Streamlit version)
MODE_AIR = "#E94B5C"        # red-warm — air, highest cost/intensity
MODE_OCEAN = "#5B8DEF"      # blue — ocean
MODE_TRUCK = "#7AA67A"      # green — truck

# Lane type colors
LT_INBOUND = "#5B8DEF"
LT_OUTBOUND = "#E59866"
LT_SERVICE = "#B084CC"
LT_INTRA = "#7AA67A"

# Contract archetype colors (severity gradient: spot=most exposed, fixed=most insulated)
ARCH_SPOT = SEV_HIGH
ARCH_INDEXED_SHORT = SEV_MED_HIGH
ARCH_INDEXED_MEDIUM = SEV_MED
ARCH_BAF_LONG = SEV_MED_LOW
ARCH_FIXED = SEV_LOW

ARCHETYPE_COLORS = {
    "spot": ARCH_SPOT,
    "indexed_short": ARCH_INDEXED_SHORT,
    "indexed_medium": ARCH_INDEXED_MEDIUM,
    "baf_long": ARCH_BAF_LONG,
    "fixed": ARCH_FIXED,
}

MODE_COLORS = {
    "air": MODE_AIR,
    "ocean": MODE_OCEAN,
    "truck": MODE_TRUCK,
}

LANE_TYPE_COLORS = {
    "inbound_component": LT_INBOUND,
    "outbound_finished": LT_OUTBOUND,
    "service_parts": LT_SERVICE,
    "intra_region_distribution": LT_INTRA,
}


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

# We use Qt's font fallback chain. Mono fonts resolve to whatever is available;
# Qt picks a good monospace on each platform.
FONT_FAMILY_BASE = "Inter, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
FONT_FAMILY_MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"

FONT_SIZE_TINY = 9
FONT_SIZE_SMALL = 10
FONT_SIZE_BASE = 11
FONT_SIZE_LARGE = 13
FONT_SIZE_HEADING = 15
FONT_SIZE_DISPLAY = 22


# ---------------------------------------------------------------------------
# Window dimensions
# ---------------------------------------------------------------------------

WINDOW_INITIAL_WIDTH = 1440
WINDOW_INITIAL_HEIGHT = 900
SIDEBAR_WIDTH = 220


# ---------------------------------------------------------------------------
# Spacing scale
# ---------------------------------------------------------------------------

SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24


# ---------------------------------------------------------------------------
# QSS — global stylesheet
# ---------------------------------------------------------------------------

def get_global_stylesheet() -> str:
    """Return the application-wide QSS stylesheet."""
    return f"""
    /* Base widget styling */
    QWidget {{
        background-color: {BG_BASE};
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY_BASE};
        font-size: {FONT_SIZE_BASE}px;
    }}

    QMainWindow {{
        background-color: {BG_DEEP};
    }}

    /* Sidebar */
    QFrame#sidebar {{
        background-color: {BG_DEEP};
        border-right: 1px solid {BORDER_SUBTLE};
    }}

    QLabel#sidebar_app_title {{
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_LARGE}px;
        font-weight: 600;
        padding: 0px;
    }}

    QLabel#sidebar_app_subtitle {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_TINY}px;
        letter-spacing: 0.05em;
    }}

    QLabel#sidebar_section_label {{
        color: {TEXT_LABEL};
        font-size: {FONT_SIZE_TINY}px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding-top: 12px;
        padding-bottom: 4px;
    }}

    QPushButton#sidebar_nav_button {{
        background-color: transparent;
        color: {TEXT_SECONDARY};
        text-align: left;
        padding: 9px 14px;
        border: none;
        border-radius: 4px;
        font-size: {FONT_SIZE_BASE}px;
    }}
    QPushButton#sidebar_nav_button:hover {{
        background-color: {BG_RAISED};
        color: {TEXT_PRIMARY};
    }}
    QPushButton#sidebar_nav_button:checked {{
        background-color: {BG_HIGHLIGHT};
        color: {TEXT_PRIMARY};
        border-left: 2px solid {ACCENT_PRIMARY};
    }}

    /* Content area */
    QFrame#content_area {{
        background-color: {BG_BASE};
    }}

    QFrame#page_header {{
        background-color: {BG_BASE};
        border-bottom: 1px solid {BORDER_SUBTLE};
    }}

    QLabel#page_title {{
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_HEADING}px;
        font-weight: 600;
    }}

    QLabel#page_subtitle {{
        color: {TEXT_SECONDARY};
        font-size: {FONT_SIZE_BASE}px;
    }}

    /* Status bar */
    QStatusBar {{
        background-color: {BG_DEEP};
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_SMALL}px;
        border-top: 1px solid {BORDER_SUBTLE};
    }}
    QStatusBar::item {{ border: none; }}

    /* Tabs */
    QTabWidget::pane {{
        border: none;
        background: {BG_BASE};
        top: 0px;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {TEXT_MUTED};
        padding: 9px 18px;
        border: none;
        border-bottom: 2px solid transparent;
        font-size: {FONT_SIZE_BASE}px;
    }}
    QTabBar::tab:hover {{
        color: {TEXT_SECONDARY};
    }}
    QTabBar::tab:selected {{
        color: {TEXT_PRIMARY};
        border-bottom: 2px solid {ACCENT_PRIMARY};
    }}

    /* Slider (shock selector) */
    QSlider::groove:horizontal {{
        height: 4px;
        background: {BORDER_STRONG};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {ACCENT_PRIMARY};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {ACCENT_HOVER};
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT_PRIMARY};
        border-radius: 2px;
    }}

    /* Scenario preset buttons */
    QPushButton#preset_button {{
        background-color: {BG_RAISED};
        color: {TEXT_SECONDARY};
        padding: 6px 8px;
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 3px;
        font-size: {FONT_SIZE_SMALL}px;
    }}
    QPushButton#preset_button:hover {{
        background-color: {BG_HIGHLIGHT};
        color: {TEXT_PRIMARY};
        border-color: {BORDER_STRONG};
    }}

    /* Generic panel ("card") */
    QFrame#panel {{
        background-color: {BG_RAISED};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: 4px;
    }}

    QFrame#panel_callout {{
        background-color: {BG_RAISED};
        border: 1px solid {BORDER_STRONG};
        border-radius: 4px;
    }}

    /* Headline number components */
    QLabel#headline_label {{
        color: {TEXT_LABEL};
        font-size: {FONT_SIZE_TINY}px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}

    QLabel#headline_value {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY_MONO};
        font-size: {FONT_SIZE_DISPLAY}px;
        font-weight: 500;
    }}

    QLabel#headline_value_large {{
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY_MONO};
        font-size: 28px;
        font-weight: 500;
    }}

    QLabel#headline_subtext {{
        color: {TEXT_SECONDARY};
        font-size: {FONT_SIZE_SMALL}px;
    }}

    /* Section headings within pages */
    QLabel#section_heading {{
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_LARGE}px;
        font-weight: 600;
        padding-top: 4px;
    }}

    QLabel#section_caption {{
        color: {TEXT_MUTED};
        font-size: {FONT_SIZE_SMALL}px;
    }}

    /* Insight footer */
    QFrame#insight_box {{
        background-color: {BG_RAISED};
        border-left: 3px solid {ACCENT_PRIMARY};
        border-top: 1px solid {BORDER_SUBTLE};
        border-right: 1px solid {BORDER_SUBTLE};
        border-bottom: 1px solid {BORDER_SUBTLE};
        border-radius: 3px;
    }}

    QLabel#insight_label {{
        color: {ACCENT_PRIMARY};
        font-size: {FONT_SIZE_TINY}px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}

    QLabel#insight_text {{
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_BASE}px;
    }}

    /* Fingerprint metrics */
    QLabel#fp_label {{
        color: {TEXT_LABEL};
        font-size: {FONT_SIZE_TINY}px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    QLabel#fp_value {{
        color: {TEXT_PRIMARY};
        font-size: {FONT_SIZE_BASE}px;
    }}

    /* Tooltips */
    QToolTip {{
        background-color: {BG_HIGHLIGHT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_STRONG};
        padding: 6px 8px;
        font-size: {FONT_SIZE_SMALL}px;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: {BG_DEEP};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_STRONG};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {TEXT_MUTED};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    """
