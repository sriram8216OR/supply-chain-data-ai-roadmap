"""
Apex HVAC Crude Exposure — desktop app entry point.

Launch with:
    python -m desktop_app.main

Or, if running as a script from the project root:
    python desktop_app/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sure project root is on path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from desktop_app import theme
from desktop_app.controller import AppController
from desktop_app.main_window import MainWindow


def main() -> int:
    # High-DPI scaling support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Apex HVAC Crude Exposure Intelligence")
    app.setStyleSheet(theme.get_global_stylesheet())

    # Build controller and load data
    data_dir = PROJECT_ROOT / "data"
    controller = AppController(data_dir)
    controller.load()

    # Show the main window
    window = MainWindow(controller)
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
