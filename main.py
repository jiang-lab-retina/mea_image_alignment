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


def main():
    """Main application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting NSEW Image Stitcher application")
    
    try:
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("NSEW Image Stitcher")
        app.setApplicationVersion("0.1.0")
        app.setOrganizationName("Image MEA Dulce")
        
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

