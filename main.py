#!/usr/bin/env python3
"""
Entry point for the deblaot GUI.

Run with:  python3 main.py
Expects a sibling ../deblaot backend folder (see deblaot_gui/backend_launcher.py).
"""
import sys
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from deblaot_gui.main_window import MainWindow
from deblaot_gui.styles import STYLESHEET


def main():
    gui_dir = Path(__file__).resolve().parent
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow(gui_dir)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
