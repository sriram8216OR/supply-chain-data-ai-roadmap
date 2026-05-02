"""
Page 1 — Executive Summary.

Two tabs:
  - Tab 1.1: Network Vulnerability Snapshot (no shock dependency)
  - Tab 1.2: Shock Impact Simulator (subscribes to controller.shock_changed)
"""

from PyQt5.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ..controller import AppController
from .page1_shock_tab import ShockTab
from .page1_vulnerability_tab import VulnerabilityTab


class Page1ExecutiveSummary(QWidget):
    def __init__(self, controller: AppController):
        super().__init__()
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(VulnerabilityTab(controller), "Network Vulnerability Snapshot")
        tabs.addTab(ShockTab(controller), "Shock Impact Simulator")
        layout.addWidget(tabs)
