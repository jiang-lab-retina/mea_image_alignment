"""
MainWindow - Primary Application Window
Main GUI interface for NSEW Image Stitcher application
"""

import logging
from pathlib import Path
from typing import Optional, Dict

import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QFileDialog, QMessageBox, QStatusBar, QToolBar, QLabel,
    QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon

from src.models import Quadrant, QuadrantImage, ImageMetadata, StitchingConfig, StitchedResult
from src.lib import keyword_detector, io, stitching, config_manager
from src.lib import CorruptedFileError, UnsupportedFormatError, FileNotFoundError, StitchingError
from src.gui.quadrant_viewer import QuadrantViewer
from src.gui.assignment_dialog import AssignmentDialog
from src.gui.stitch_dialog import StitchDialog
from src.gui.result_window import ResultWindow

logger = logging.getLogger(__name__)


class StitchingThread(QThread):
    """Background thread for stitching operations."""
    
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(object)  # StitchedResult
    error = pyqtSignal(str)
    
    def __init__(self, quadrant_images: list, config: StitchingConfig):
        super().__init__()
        self.quadrant_images = quadrant_images
        self.config = config
    
    def run(self):
        """Execute stitching in background."""
        try:
            result = stitching.stitch_quadrants(
                self.quadrant_images,
                self.config,
                progress_callback=self._progress_callback
            )
            self.finished.emit(result)
        except Exception as e:
            logger.exception("Stitching failed")
            self.error.emit(str(e))
    
    def _progress_callback(self, percent: int, message: str):
        """Forward progress updates to main thread."""
        self.progress_updated.emit(percent, message)


class MainWindow(QMainWindow):
    """
    Main application window for NSEW Image Stitcher.
    
    Features:
    - Menu bar and toolbar with actions
    - 2x2 grid layout for four QuadrantViewer widgets
    - File loading with automatic keyword detection
    - Manual quadrant assignment for ambiguous files
    - Synchronized zoom and pan across all quadrants
    - Status bar for operation feedback
    
    Layout:
        Toolbar: [Load Images] [Stitch Images] [Save Config]
        Grid:    [ NW | NE ]
                 [ SW | SE ]
        Status:  "Ready" / "Loaded X of Y files"
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize main window."""
        super().__init__(parent)
        
        self.loaded_images: Dict[Quadrant, QuadrantImage] = {}
        self.quadrant_viewers: Dict[Quadrant, QuadrantViewer] = {}
        self.last_result: Optional[StitchedResult] = None
        self.stitching_thread: Optional[StitchingThread] = None
        self.progress_dialog: Optional[QProgressDialog] = None
        
        self._setup_ui()
        self._connect_signals()
        
        logger.info("MainWindow initialized")
    
    def _setup_ui(self):
        """Set up window layout and components."""
        self.setWindowTitle("NSEW Image Stitcher - Image MEA Dulce")
        self.setMinimumSize(1200, 800)
        
        # Create central widget with grid layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Title header
        title_label = QLabel("<h2>NSEW Image Stitcher</h2>")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #2e7d32;
                padding: 8px;
                background-color: #f1f8e9;
                border-radius: 4px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize() * 1.2)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 4px;
                spacing: 8px;
            }
            QToolButton {
                padding: 8px 12px;
                border-radius: 3px;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #e8f5e9;
            }
        """)
        
        # Load Images action
        load_action = QAction("📁 Load Images", self)
        load_action.setStatusTip("Load microscopy images with NSEW keywords")
        load_action.triggered.connect(self.on_open_files_clicked)
        toolbar.addAction(load_action)
        
        # Auto-Load action
        auto_load_action = QAction("🔍 Auto-Load", self)
        auto_load_action.setStatusTip("Select one image and automatically find matching NSEW quadrants")
        auto_load_action.triggered.connect(self.on_auto_load_clicked)
        toolbar.addAction(auto_load_action)
        
        toolbar.addSeparator()
        
        # Stitch Images action (initially disabled)
        self.stitch_action = QAction("🔗 Stitch Images", self)
        self.stitch_action.setStatusTip("Stitch loaded quadrant images into panorama")
        self.stitch_action.setEnabled(False)
        self.stitch_action.triggered.connect(self.on_stitch_clicked)
        toolbar.addAction(self.stitch_action)
        
        toolbar.addSeparator()
        
        # Save Config action (initially disabled)
        self.save_config_action = QAction("💾 Save Config", self)
        self.save_config_action.setStatusTip("Save stitching configuration to file")
        self.save_config_action.setEnabled(False)
        # Will be connected later
        toolbar.addAction(self.save_config_action)
        
        self.addToolBar(toolbar)
        
        # 2x2 grid for quadrant viewers
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)
        
        # Create quadrant viewers
        for quadrant in Quadrant:
            viewer = QuadrantViewer()
            self.quadrant_viewers[quadrant] = viewer
            
            # Position in grid based on quadrant
            row, col = quadrant.position_indices()
            grid_layout.addWidget(viewer, row, col)
            
            # Set initial placeholder
            viewer.position_label.setText(quadrant.label)
        
        main_layout.addLayout(grid_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #fafafa;
                border-top: 1px solid #e0e0e0;
                padding: 4px;
                font-size: 10px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Load microscopy images to begin")
    
    def _connect_signals(self):
        """Connect signals between quadrant viewers for synchronization."""
        # Connect zoom signals from each viewer to sync_zoom_to_all
        for viewer in self.quadrant_viewers.values():
            viewer.zoom_changed.connect(self._sync_zoom_to_all)
            viewer.pan_changed.connect(self._sync_pan_to_all)
    
    def on_auto_load_clicked(self):
        """Handle Auto-Load button click."""
        # Show file dialog to select one reference image
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Select Reference Image (will auto-find matching quadrants)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)  # Single file
        file_dialog.setNameFilter(
            "Microscopy Images (*.czi *.lsm *.tif *.tiff);;All Files (*)"
        )
        
        if file_dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        
        selected_files = file_dialog.selectedFiles()
        if not selected_files:
            return
        
        reference_path = Path(selected_files[0])
        logger.info(f"Auto-load reference: {reference_path.name}")
        
        # Extract prefix by using last 2 characters as quadrant identifier
        filename_stem = reference_path.stem  # Filename without extension
        
        # Get last 2 characters (should be NE, NW, SE, or SW)
        if len(filename_stem) < 2:
            QMessageBox.warning(
                self,
                "Invalid Filename",
                f"Filename too short to extract quadrant:\n{reference_path.name}",
                QMessageBox.StandardButton.Ok
            )
            return
        
        last_two_chars = filename_stem[-2:].upper()
        
        # Validate it's a valid quadrant identifier
        valid_quadrants = ["NE", "NW", "SE", "SW"]
        if last_two_chars not in valid_quadrants:
            QMessageBox.warning(
                self,
                "No Quadrant Identifier Found",
                f"Last 2 characters '{last_two_chars}' are not a valid quadrant (NE, NW, SE, SW).\n\n"
                f"Filename: {reference_path.name}\n\n"
                "Please ensure filenames end with NE, NW, SE, or SW before the extension.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Extract prefix (everything except last 2 characters)
        prefix = filename_stem[:-2]
        logger.info(f"Extracted prefix: '{prefix}', detected quadrant: {last_two_chars}")
        
        # Search for matching files in the same directory
        directory = reference_path.parent
        extension = reference_path.suffix
        
        found_files = []
        found_quadrants = []
        
        # Look for files with pattern: prefix + NE/NW/SE/SW + extension
        for quadrant_str in ["NE", "NW", "SE", "SW"]:
            candidate_name = f"{prefix}{quadrant_str}{extension}"
            candidate_path = directory / candidate_name
            
            if candidate_path.exists():
                # Map string to Quadrant enum
                quadrant = Quadrant[quadrant_str]
                found_files.append(candidate_path)
                found_quadrants.append(quadrant)
                logger.info(f"Found {quadrant.value}: {candidate_path.name}")
        
        if not found_files:
            QMessageBox.warning(
                self,
                "No Matching Files Found",
                f"Could not find matching quadrant images with prefix:\n{prefix}\n\n"
                f"Searched in: {directory}\n"
                f"Looking for files like:\n"
                f"• {prefix}NE{extension}\n"
                f"• {prefix}NW{extension}\n"
                f"• {prefix}SE{extension}\n"
                f"• {prefix}SW{extension}",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Show confirmation dialog
        file_list = "\n".join([f"• {quadrant.value}: {path.name}" 
                               for quadrant, path in zip(found_quadrants, found_files)])
        
        reply = QMessageBox.question(
            self,
            "Auto-Load Confirmation",
            f"Found {len(found_files)} matching quadrant image(s):\n\n"
            f"{file_list}\n\n"
            "Load these images?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"Auto-loading {len(found_files)} files")
            self.load_files(found_files)
    
    def on_open_files_clicked(self):
        """Handle Load Images button click."""
        # Show file dialog
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Select Microscopy Images")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter(
            "Microscopy Images (*.czi *.lsm *.tif *.tiff);;All Files (*)"
        )
        
        if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
            file_paths = [Path(p) for p in file_dialog.selectedFiles()]
            logger.info(f"User selected {len(file_paths)} files")
            self.load_files(file_paths)
    
    def load_files(self, file_paths: list[Path]):
        """
        Load microscopy images from file paths.
        
        For each file:
        1. Load image data and metadata using lib.io.load_image()
        2. Detect quadrant position using lib.keyword_detector.detect_quadrant()
        3. If detection fails, show AssignmentDialog for manual assignment
        4. Handle errors gracefully, showing warnings but continuing with remaining files
        5. Update QuadrantViewer widgets with loaded images
        
        Args:
            file_paths: List of Paths to microscopy image files
        """
        loaded_count = 0
        failed_files = []
        
        for file_path in file_paths:
            try:
                # Load image data and metadata
                logger.info(f"Loading {file_path.name}...")
                image_data, metadata = io.load_image(file_path)
                
                # Detect quadrant from filename
                detected_quadrant = keyword_detector.detect_quadrant(file_path.name)
                
                # If detection failed, show assignment dialog
                if detected_quadrant is None:
                    logger.info(f"Ambiguous keywords in {file_path.name}, showing assignment dialog")
                    
                    # Create thumbnail for preview (downsample to 256x256)
                    thumbnail = self._create_thumbnail(image_data, max_size=256)
                    
                    dialog = AssignmentDialog(
                        filename=file_path.name,
                        image_preview=thumbnail,
                        parent=self
                    )
                    
                    if dialog.exec() == AssignmentDialog.DialogCode.Accepted:
                        detected_quadrant = dialog.get_selected_quadrant()
                    else:
                        # User cancelled assignment
                        logger.info(f"User cancelled assignment for {file_path.name}")
                        continue
                
                # Check if quadrant is already occupied
                if detected_quadrant in self.loaded_images:
                    # Ask user if they want to replace
                    existing_file = self.loaded_images[detected_quadrant].filename
                    reply = QMessageBox.question(
                        self,
                        "Replace Existing Image?",
                        f"The {detected_quadrant.label} quadrant already contains:\n{existing_file}\n\n"
                        f"Do you want to replace it with:\n{file_path.name}",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if reply != QMessageBox.StandardButton.Yes:
                        continue
                
                # Create QuadrantImage object
                quadrant_image = QuadrantImage(
                    file_path=file_path,
                    quadrant=detected_quadrant,
                    filename=file_path.name,
                    dimensions=(image_data.shape[0], image_data.shape[1]),
                    dtype=image_data.dtype,
                    num_channels=image_data.shape[2] if image_data.ndim == 3 else 1,
                    file_size_bytes=file_path.stat().st_size,
                    image_data=image_data,
                    metadata=metadata
                )
                
                # Compute and store checksum
                quadrant_image.md5_checksum = quadrant_image.compute_checksum()
                
                # Store in loaded_images dict
                self.loaded_images[detected_quadrant] = quadrant_image
                
                # Update corresponding QuadrantViewer
                viewer = self.quadrant_viewers[detected_quadrant]
                viewer.set_image(quadrant_image)
                
                loaded_count += 1
                logger.info(
                    f"Successfully loaded {file_path.name} into {detected_quadrant.label} quadrant"
                )
            
            except CorruptedFileError as e:
                # Show warning but continue with remaining files
                logger.warning(f"Corrupted file: {file_path.name}")
                failed_files.append((file_path.name, str(e)))
                
                QMessageBox.warning(
                    self,
                    "Corrupted File",
                    f"Cannot read file: {file_path.name}\n\n"
                    f"The file may be corrupted or invalid.\n\n"
                    f"Error: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )
            
            except UnsupportedFormatError as e:
                # Show warning but continue
                logger.warning(f"Unsupported format: {file_path.name}")
                failed_files.append((file_path.name, str(e)))
                
                QMessageBox.warning(
                    self,
                    "Unsupported Format",
                    f"File format not supported: {file_path.name}\n\n"
                    f"Supported formats: .czi, .lsm, .tif, .tiff\n\n"
                    f"Error: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )
            
            except FileNotFoundError as e:
                # Show warning but continue
                logger.warning(f"File not found: {file_path.name}")
                failed_files.append((file_path.name, str(e)))
                
                QMessageBox.warning(
                    self,
                    "File Not Found",
                    f"File not found: {file_path.name}\n\n"
                    f"Error: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )
            
            except Exception as e:
                # Catch any unexpected errors
                logger.exception(f"Unexpected error loading {file_path.name}")
                failed_files.append((file_path.name, f"Unexpected error: {str(e)}"))
                
                QMessageBox.critical(
                    self,
                    "Unexpected Error",
                    f"Unexpected error loading file: {file_path.name}\n\n"
                    f"Error: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )
        
        # Update status bar
        total_files = len(file_paths)
        if loaded_count > 0:
            status_msg = f"Loaded {loaded_count} of {total_files} file(s)"
            if failed_files:
                status_msg += f" ({len(failed_files)} failed)"
            self.status_bar.showMessage(status_msg)
            
            # Enable Stitch button if at least 1 image loaded
            self.stitch_action.setEnabled(True)
        else:
            self.status_bar.showMessage(f"No files loaded successfully (0 of {total_files})")
        
        logger.info(f"File loading complete: {loaded_count}/{total_files} successful")
    
    def _create_thumbnail(self, image_data: np.ndarray, max_size: int = 256) -> np.ndarray:
        """
        Create thumbnail preview of image for dialog display.
        
        Args:
            image_data: Full-resolution image array
            max_size: Maximum dimension for thumbnail
            
        Returns:
            Downsampled image array
        """
        height, width = image_data.shape[:2]
        
        if max(height, width) <= max_size:
            return image_data
        
        # Calculate scale factor
        scale = max_size / max(height, width)
        new_height = int(height * scale)
        new_width = int(width * scale)
        
        # Simple downsampling using array slicing
        step_h = max(1, height // new_height)
        step_w = max(1, width // new_width)
        
        if image_data.ndim == 2:
            thumbnail = image_data[::step_h, ::step_w]
        else:
            thumbnail = image_data[::step_h, ::step_w, :]
        
        return thumbnail
    
    def _sync_zoom_to_all(self, zoom_level: float):
        """
        Synchronize zoom level to all quadrant viewers.
        
        Called when any viewer's zoom changes.
        
        Args:
            zoom_level: New zoom level to apply to all viewers
        """
        sender_viewer = self.sender()
        
        for viewer in self.quadrant_viewers.values():
            if viewer != sender_viewer:
                viewer.sync_zoom(zoom_level)
    
    def _sync_pan_to_all(self, dx: int, dy: int):
        """
        Synchronize pan offset to all quadrant viewers.
        
        Called when any viewer's pan changes.
        
        Args:
            dx: Horizontal pan delta in pixels
            dy: Vertical pan delta in pixels
        """
        sender_viewer = self.sender()
        
        for viewer in self.quadrant_viewers.values():
            if viewer != sender_viewer:
                viewer.sync_pan(dx, dy)
    
    def on_stitch_clicked(self):
        """Handle Stitch Images button click."""
        if not self.loaded_images:
            QMessageBox.warning(
                self,
                "No Images Loaded",
                "Please load at least one image before stitching.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Show dimension mismatch notification if needed
        dimensions = [img.dimensions for img in self.loaded_images.values()]
        if len(set(dimensions)) > 1:
            dim_str = ", ".join([f"{w}×{h}" for h, w in dimensions])
            QMessageBox.information(
                self,
                "Dimension Mismatch Detected",
                f"Images have different dimensions: {dim_str}\n\n"
                "Images will be automatically resized to match during stitching.",
                QMessageBox.StandardButton.Ok
            )
        
        # Show stitch dialog to get parameters
        dialog = StitchDialog(parent=self)
        if dialog.exec() != StitchDialog.DialogCode.Accepted:
            return
        
        config = dialog.get_config()
        logger.info(f"Starting stitching with config: {config}")
        
        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            "Preparing to stitch images...",
            "Cancel",
            0,
            100,
            self
        )
        self.progress_dialog.setWindowTitle("Stitching in Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        
        # Create and start stitching thread
        quadrant_list = list(self.loaded_images.values())
        self.stitching_thread = StitchingThread(quadrant_list, config)
        
        # Connect signals
        self.stitching_thread.progress_updated.connect(self._handle_stitching_progress)
        self.stitching_thread.finished.connect(self._handle_stitching_complete)
        self.stitching_thread.error.connect(self._handle_stitching_error)
        self.progress_dialog.canceled.connect(self.stitching_thread.terminate)
        
        # Start stitching
        self.stitching_thread.start()
        self.status_bar.showMessage("Stitching in progress...")
    
    def _handle_stitching_progress(self, percent: int, message: str):
        """Handle progress updates from stitching thread."""
        if self.progress_dialog:
            self.progress_dialog.setValue(percent)
            self.progress_dialog.setLabelText(message)
    
    def _handle_stitching_complete(self, result: StitchedResult):
        """Handle successful stitching completion."""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        self.last_result = result
        self.save_config_action.setEnabled(True)
        
        logger.info(f"Stitching complete: {result.full_width}×{result.full_height}px")
        
        # Show result window
        result_window = ResultWindow(result, parent=self)
        result_window.show()
        
        self.status_bar.showMessage(
            f"Stitching complete! Quality: {result.quality_metrics.quality_category()}"
        )
        
        # Show success message
        QMessageBox.information(
            self,
            "✅ Stitching Complete!",
            f"Successfully stitched {result.num_quadrants_used()} quadrant(s).\n\n"
            f"Resolution: {result.full_width} × {result.full_height} pixels\n"
            f"Quality: {result.quality_metrics.quality_category()} "
            f"({result.quality_metrics.overall_confidence:.2f})\n"
            f"Processing time: {result.processing_time_seconds:.2f} seconds",
            QMessageBox.StandardButton.Ok
        )
    
    def _handle_stitching_error(self, error_message: str):
        """Handle stitching errors."""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        logger.error(f"Stitching failed: {error_message}")
        
        self.status_bar.showMessage("Stitching failed")
        
        # Show error with actionable guidance
        QMessageBox.critical(
            self,
            "❌ Stitching Failed",
            f"Could not stitch images:\n\n{error_message}\n\n"
            "Suggestions:\n"
            "• Ensure images have sufficient overlap (10-20%)\n"
            "• Try different alignment method (ORB, SIFT, AKAZE)\n"
            "• Check that images are from the same sample\n"
            "• Verify images are not corrupted",
            QMessageBox.StandardButton.Ok
        )
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Terminate stitching thread if running
        if self.stitching_thread and self.stitching_thread.isRunning():
            self.stitching_thread.terminate()
            self.stitching_thread.wait()
        
        logger.info("MainWindow closing")
        event.accept()

