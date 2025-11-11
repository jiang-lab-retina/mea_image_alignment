#!/usr/bin/env python3
"""
NSEW Image Stitcher - Application Entry Point
Multi-Electrode Array (MEA) microscopy image stitching application

This application enables researchers to load, visualize, and stitch
microscopy images arranged in spatial quadrants (North, South, East, West).
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication


def setup_logging():
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )


def get_dark_mode_stylesheet():
    """Return a comprehensive dark mode stylesheet for the application."""
    return """
    /* Main Application Background */
    QMainWindow, QDialog, QWidget {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
    
    /* Toolbar Styling */
    QToolBar {
        background-color: #252525;
        border: none;
        border-bottom: 1px solid #3d3d3d;
        spacing: 8px;
        padding: 4px;
    }
    
    QToolBar QToolButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        padding: 6px 12px;
        margin: 2px;
    }
    
    QToolBar QToolButton:hover {
        background-color: #3d3d3d;
        border-color: #4d4d4d;
    }
    
    QToolBar QToolButton:pressed {
        background-color: #1a1a1a;
    }
    
    QToolBar QToolButton:disabled {
        background-color: #222222;
        color: #666666;
        border-color: #2d2d2d;
    }
    
    /* Menu Bar */
    QMenuBar {
        background-color: #252525;
        color: #e0e0e0;
        border-bottom: 1px solid #3d3d3d;
    }
    
    QMenuBar::item {
        background-color: transparent;
        padding: 4px 12px;
    }
    
    QMenuBar::item:selected {
        background-color: #3d3d3d;
    }
    
    QMenu {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
    }
    
    QMenu::item {
        padding: 6px 24px;
    }
    
    QMenu::item:selected {
        background-color: #3d3d3d;
    }
    
    /* Push Buttons */
    QPushButton {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        padding: 6px 16px;
        min-height: 24px;
    }
    
    QPushButton:hover {
        background-color: #3d3d3d;
        border-color: #4d4d4d;
    }
    
    QPushButton:pressed {
        background-color: #1a1a1a;
    }
    
    QPushButton:disabled {
        background-color: #222222;
        color: #666666;
        border-color: #2d2d2d;
    }
    
    /* Status Bar */
    QStatusBar {
        background-color: #252525;
        color: #e0e0e0;
        border-top: 1px solid #3d3d3d;
    }
    
    /* Labels */
    QLabel {
        color: #e0e0e0;
        background-color: transparent;
    }
    
    /* Group Boxes */
    QGroupBox {
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
        font-weight: bold;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }
    
    /* Line Edit */
    QLineEdit {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        padding: 4px 8px;
        selection-background-color: #0d7377;
    }
    
    QLineEdit:focus {
        border-color: #0d7377;
    }
    
    /* Text Edit */
    QTextEdit, QPlainTextEdit {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        selection-background-color: #0d7377;
    }
    
    /* Combo Box */
    QComboBox {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        padding: 4px 8px;
    }
    
    QComboBox:hover {
        border-color: #4d4d4d;
    }
    
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    
    QComboBox QAbstractItemView {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        selection-background-color: #3d3d3d;
    }
    
    /* Spin Box */
    QSpinBox, QDoubleSpinBox {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        padding: 4px 8px;
    }
    
    /* Check Box */
    QCheckBox {
        color: #e0e0e0;
        spacing: 8px;
    }
    
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #3d3d3d;
        border-radius: 3px;
        background-color: #2d2d2d;
    }
    
    QCheckBox::indicator:hover {
        border-color: #4d4d4d;
    }
    
    QCheckBox::indicator:checked {
        background-color: #0d7377;
        border-color: #0d7377;
    }
    
    /* Radio Button */
    QRadioButton {
        color: #e0e0e0;
        spacing: 8px;
    }
    
    QRadioButton::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #3d3d3d;
        border-radius: 8px;
        background-color: #2d2d2d;
    }
    
    QRadioButton::indicator:checked {
        background-color: #0d7377;
        border-color: #0d7377;
    }
    
    /* Scroll Bar */
    QScrollBar:vertical {
        background-color: #1e1e1e;
        width: 12px;
        border: none;
    }
    
    QScrollBar::handle:vertical {
        background-color: #3d3d3d;
        min-height: 20px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:vertical:hover {
        background-color: #4d4d4d;
    }
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
    
    QScrollBar:horizontal {
        background-color: #1e1e1e;
        height: 12px;
        border: none;
    }
    
    QScrollBar::handle:horizontal {
        background-color: #3d3d3d;
        min-width: 20px;
        border-radius: 6px;
    }
    
    QScrollBar::handle:horizontal:hover {
        background-color: #4d4d4d;
    }
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    
    /* Tab Widget */
    QTabWidget::pane {
        border: 1px solid #3d3d3d;
        background-color: #1e1e1e;
    }
    
    QTabBar::tab {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        padding: 6px 12px;
        margin-right: 2px;
    }
    
    QTabBar::tab:selected {
        background-color: #1e1e1e;
        border-bottom: 2px solid #0d7377;
    }
    
    QTabBar::tab:hover:!selected {
        background-color: #3d3d3d;
    }
    
    /* Progress Bar */
    QProgressBar {
        background-color: #2d2d2d;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
        text-align: center;
        color: #e0e0e0;
    }
    
    QProgressBar::chunk {
        background-color: #0d7377;
        border-radius: 3px;
    }
    
    /* Dialog Buttons */
    QDialogButtonBox QPushButton {
        min-width: 80px;
    }
    
    /* Message Box */
    QMessageBox {
        background-color: #1e1e1e;
    }
    
    QMessageBox QLabel {
        color: #e0e0e0;
    }
    
    /* Tool Tip */
    QToolTip {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        padding: 4px;
    }
    
    /* List Widget */
    QListWidget {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
    }
    
    QListWidget::item:selected {
        background-color: #3d3d3d;
    }
    
    QListWidget::item:hover {
        background-color: #353535;
    }
    
    /* Tree Widget */
    QTreeWidget {
        background-color: #2d2d2d;
        color: #e0e0e0;
        border: 1px solid #3d3d3d;
        border-radius: 4px;
    }
    
    QTreeWidget::item:selected {
        background-color: #3d3d3d;
    }
    
    QTreeWidget::item:hover {
        background-color: #353535;
    }
    
    /* Splitter */
    QSplitter::handle {
        background-color: #3d3d3d;
    }
    
    QSplitter::handle:hover {
        background-color: #4d4d4d;
    }
    """


def main():
    """Main application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting NSEW Image Stitcher application")
    
    try:
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("NSEW Image Stitcher")
        app.setApplicationVersion("0.2.0")
        app.setOrganizationName("Image MEA Dulce")
        
        # Apply dark mode stylesheet
        app.setStyleSheet(get_dark_mode_stylesheet())
        logger.info("Dark mode theme applied")
        
        # Import here to avoid circular imports
        from src.gui.main_window import MainWindow
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        logger.info("Application initialized successfully")
        
        # Start event loop
        sys.exit(app.exec())
        
    except Exception as e:
        logger.exception(f"Fatal error during application startup: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

