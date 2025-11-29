#!/usr/bin/env python3
"""
ns-3 Network Simulator GUI - Main Entry Point

A visual interface for designing and simulating network topologies
using the ns-3 discrete-event network simulator.

Usage:
    python main.py
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette, QColor

from views import MainWindow


def setup_application() -> QApplication:
    """Configure the Qt application."""
    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("ns-3 GUI")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("ns3-gui")
    
    # Set default font
    font = QFont("SF Pro Display", 10)
    if not font.exactMatch():
        font = QFont("Segoe UI", 10)
    if not font.exactMatch():
        font = QFont("Helvetica Neue", 10)
    app.setFont(font)
    
    # Set up palette for consistent look
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#F3F4F6"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#111827"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#F9FAFB"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#374151"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#374151"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3B82F6"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)
    
    return app


def main():
    """Main entry point."""
    app = setup_application()
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
