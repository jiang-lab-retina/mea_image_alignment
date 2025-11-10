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
from src.models.alignment_parameters import AlignmentParameters
from src.lib import keyword_detector, io, stitching, config_manager, alignment_manager, chip_image_finder, chip_stitcher
from src.lib import CorruptedFileError, UnsupportedFormatError, FileNotFoundError, StitchingError, ChipImageNotFoundError
from src.models.chip_image_set import ChipImageSet
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


class ChipStitchingThread(QThread):
    """Background thread for chip stitching operations (T050)."""
    
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(object)  # StitchedResult
    error = pyqtSignal(str)
    
    def __init__(self, chip_image_set: ChipImageSet, alignment_params: AlignmentParameters, config: StitchingConfig):
        super().__init__()
        self.chip_image_set = chip_image_set
        self.alignment_params = alignment_params
        self.config = config
    
    def run(self):
        """Execute chip stitching in background."""
        try:
            result = chip_stitcher.stitch_chip_images(
                self.chip_image_set,
                self.alignment_params,
                self.config,
                progress_callback=self._progress_callback
            )
            self.finished.emit(result)
        except Exception as e:
            logger.exception("Chip stitching failed")
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
        
        # Chip stitching state (T021)
        self.alignment_parameters: Optional[AlignmentParameters] = None
        self.chip_stitching_thread: Optional[ChipStitchingThread] = None
        self.chip_progress_dialog: Optional[QProgressDialog] = None
        
        self._setup_ui()
        self._connect_signals()
        
        # Load saved alignment parameters if available (T025)
        self.load_saved_alignment_params()
        
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
        
        # Stitch Chip Images action (initially disabled) (T020)
        self.stitch_chip_action = QAction("🔬 Stitch Chip Images", self)
        self.stitch_chip_action.setStatusTip("Apply alignment to stitch chip images (requires previous stitching)")
        self.stitch_chip_action.setEnabled(False)
        self.stitch_chip_action.triggered.connect(self.on_stitch_chip_clicked)
        toolbar.addAction(self.stitch_chip_action)
        
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
        try:
            if self.progress_dialog:
                self.progress_dialog.setValue(percent)
                self.progress_dialog.setLabelText(message)
        except Exception as e:
            logger.error(f"Error updating progress: {e}")
    
    def _handle_stitching_complete(self, result: StitchedResult):
        """Handle successful stitching completion."""
        try:
            # Close progress dialog first
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
            
            # Store result
            self.last_result = result
            self.save_config_action.setEnabled(True)
            
            # Store alignment parameters and enable chip stitching (T023-T024)
            if result.alignment_parameters:
                self.alignment_parameters = result.alignment_parameters
                self._save_alignment_params_to_disk()
                self.stitch_chip_action.setEnabled(True)
                logger.info("Alignment parameters captured and saved - chip stitching enabled")
            else:
                logger.warning("No alignment parameters in result - chip stitching disabled")
            
            logger.info(f"Stitching complete: {result.full_width}×{result.full_height}px")
            
            # Update status bar (simpler message to avoid potential errors)
            self.status_bar.showMessage(f"Stitching complete! {result.full_width}×{result.full_height}px")
            
            # Show result window
            try:
                result_window = ResultWindow(result, parent=self)
                result_window.show()
            except Exception as e:
                logger.exception("Error creating result window")
                QMessageBox.warning(
                    self,
                    "Display Error",
                    f"Stitching succeeded but could not display result:\n{str(e)}\n\n"
                    f"Result saved to: {result.timestamp}",
                    QMessageBox.StandardButton.Ok
                )
                return
            
            # Show success message with careful formatting
            try:
                quality_info = ""
                if result.quality_metrics:
                    try:
                        quality_cat = result.quality_metrics.quality_category()
                        confidence = result.quality_metrics.overall_confidence
                        quality_info = f"Quality: {quality_cat} ({confidence:.2f})\n"
                    except:
                        quality_info = ""
                
                num_quadrants = len(result.source_quadrants)
                
                QMessageBox.information(
                    self,
                    "Stitching Complete",
                    f"Successfully stitched {num_quadrants} quadrant(s).\n\n"
                    f"Resolution: {result.full_width} × {result.full_height} pixels\n"
                    f"{quality_info}"
                    f"Processing time: {result.processing_time_seconds:.2f} seconds",
                    QMessageBox.StandardButton.Ok
                )
            except Exception as e:
                logger.exception("Error showing success message")
                # Still show a simple success message
                QMessageBox.information(
                    self,
                    "Stitching Complete",
                    "Image stitching completed successfully!",
                    QMessageBox.StandardButton.Ok
                )
        
        except Exception as e:
            logger.exception("Critical error in stitching completion handler")
            # Ensure progress dialog is closed
            if self.progress_dialog:
                try:
                    self.progress_dialog.close()
                    self.progress_dialog = None
                except:
                    pass
            
            # Show error message
            QMessageBox.critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred after stitching:\n\n{str(e)}\n\n"
                "The stitching may have completed, but the result could not be displayed.",
                QMessageBox.StandardButton.Ok
            )
            self.status_bar.showMessage("Error displaying stitching result")
    
    def _handle_stitching_error(self, error_message: str):
        """Handle stitching errors."""
        try:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
            
            logger.error(f"Stitching failed: {error_message}")
            
            self.status_bar.showMessage("Stitching failed")
            
            # Show error with actionable guidance
            QMessageBox.critical(
                self,
                "Stitching Failed",
                f"Could not stitch images:\n\n{error_message}\n\n"
                "Suggestions:\n"
                "• Ensure images have sufficient overlap (10-20%)\n"
                "• Try different alignment method (ORB, SIFT, AKAZE)\n"
                "• Check that images are from the same sample\n"
                "• Verify images are not corrupted",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            logger.exception("Critical error in stitching error handler")
            # Fallback error message
            try:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Stitching failed: {error_message}",
                    QMessageBox.StandardButton.Ok
                )
            except:
                pass
    
    def _save_alignment_params_to_disk(self):
        """
        Save alignment parameters to disk (T024).
        
        Saves to ./.image_mea_alignment_params.json alongside the stitched image.
        Uses atomic write to prevent corruption.
        """
        if not self.alignment_parameters:
            return
        
        try:
            # Save to current directory
            save_path = Path.cwd() / ".image_mea_alignment_params.json"
            alignment_manager.save_alignment_params(self.alignment_parameters, save_path)
            logger.info(f"Saved alignment parameters to: {save_path}")
        except Exception as e:
            logger.exception("Failed to save alignment parameters")
            QMessageBox.warning(
                self,
                "Save Warning",
                f"Could not save alignment parameters:\n{str(e)}\n\n"
                "Chip stitching will work for this session but parameters won't persist.",
                QMessageBox.StandardButton.Ok
            )
    
    def load_saved_alignment_params(self):
        """
        Load previously saved alignment parameters (T025-T026).
        
        Checks for ./.image_mea_alignment_params.json and validates:
        - File format and completeness
        - Parameter version compatibility
        - Referenced image files existence
        
        Shows warnings for corrupted/incomplete files.
        Enables chip stitching button if valid parameters found.
        """
        try:
            param_path = Path.cwd() / ".image_mea_alignment_params.json"
            
            if not param_path.exists():
                logger.debug("No saved alignment parameters found")
                return
            
            # Load parameters
            params = alignment_manager.load_alignment_params(param_path)
            
            # Validate parameters (T026)
            validation = alignment_manager.validate_alignment_params(
                params, 
                check_file_existence=True
            )
            
            if not validation.is_valid:
                # Show warning about corrupted/incomplete file
                error_details = "\n".join(f"  • {err}" for err in validation.errors)
                warning_details = "\n".join(f"  • {warn}" for warn in validation.warnings) if validation.warnings else ""
                
                message = f"Found alignment parameter file, but it has issues:\n\n{error_details}"
                if warning_details:
                    message += f"\n\nWarnings:\n{warning_details}"
                message += "\n\nChip stitching will be disabled until you perform a new stitch."
                
                QMessageBox.warning(
                    self,
                    "Invalid Alignment Parameters",
                    message,
                    QMessageBox.StandardButton.Ok
                )
                logger.warning(f"Invalid alignment parameters: {', '.join(validation.errors)}")
                return
            
            # Parameters are valid - enable chip stitching
            self.alignment_parameters = params
            self.stitch_chip_action.setEnabled(True)
            
            # Show info message about warnings if any
            if validation.warnings:
                warning_details = "\n".join(f"  • {warn}" for warn in validation.warnings)
                QMessageBox.information(
                    self,
                    "Alignment Parameters Loaded",
                    f"Loaded previous alignment parameters with warnings:\n\n{warning_details}\n\n"
                    "Chip stitching is enabled, but results may vary if referenced images have changed.",
                    QMessageBox.StandardButton.Ok
                )
                logger.info(f"Loaded alignment parameters with warnings: {', '.join(validation.warnings)}")
            else:
                logger.info(f"Successfully loaded alignment parameters from: {param_path}")
                self.status_bar.showMessage("Loaded previous alignment - chip stitching enabled")
        
        except Exception as e:
            logger.exception("Error loading alignment parameters")
            QMessageBox.warning(
                self,
                "Load Error",
                f"Could not load alignment parameters:\n{str(e)}\n\n"
                "Chip stitching will be disabled.",
                QMessageBox.StandardButton.Ok
            )
    
    def on_stitch_chip_clicked(self):
        """
        Handle chip stitching button click (T033-T035).
        
        Workflow:
        1. Discover chip images using alignment parameters (T033)
        2. Display error if no chip images found (T034)
        3. Show discovery results summary before proceeding (T035)
        4. Proceed to chip stitching (Phase 5 implementation)
        """
        logger.info("Chip stitching button clicked")
        
        if not self.alignment_parameters:
            QMessageBox.warning(
                self,
                "No Alignment Parameters",
                "Cannot stitch chip images: no alignment parameters available.\n\n"
                "Please perform original stitching first.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        try:
            # T033: Discover chip images
            logger.info("Discovering chip images...")
            chip_set = chip_image_finder.find_chip_images(self.alignment_parameters)
            
            # T035: Show discovery results summary
            found_count = len(chip_set.chip_images)
            missing_count = len(chip_set.missing_quadrants)
            mismatch_count = len(chip_set.dimension_mismatches)
            total_count = found_count + missing_count
            
            # Build detailed summary message
            summary_lines = [
                f"Chip Image Discovery Results:",
                f"",
            ]
            
            # Show status based on what was found
            if found_count == 0:
                summary_lines.append(f"⚠️ Found: {found_count} of {total_count} chip images (ALL MISSING)")
                summary_lines.append(f"All quadrants will use black placeholders.")
            elif found_count == total_count:
                summary_lines.append(f"✓ Found: {found_count} of {total_count} chip images (ALL FOUND)")
            else:
                summary_lines.append(f"✓ Found: {found_count} of {total_count} chip images")
            
            # List found chips
            if chip_set.chip_images:
                summary_lines.append("")
                summary_lines.append("Found chips:")
                for quadrant, path in chip_set.chip_images.items():
                    summary_lines.append(f"  • {quadrant.value}: {path.name}")
            
            # List missing chips (will use placeholders)
            if chip_set.missing_quadrants:
                summary_lines.append("")
                summary_lines.append(f"⚠️ Missing: {missing_count} chip images (will use black placeholders):")
                for quadrant in chip_set.missing_quadrants:
                    summary_lines.append(f"  • {quadrant.value}")
            
            # List dimension mismatches (will be resized)
            if chip_set.dimension_mismatches:
                summary_lines.append("")
                summary_lines.append(f"📐 Dimension mismatches: {mismatch_count} (will be automatically resized):")
                for mismatch in chip_set.dimension_mismatches:
                    summary_lines.append(
                        f"  • {mismatch.quadrant.value}: "
                        f"{mismatch.actual_dimensions} → {mismatch.expected_dimensions}"
                    )
            
            summary_lines.append("")
            summary_lines.append("Proceed with chip stitching?")
            
            # Show confirmation dialog with discovery results
            result = QMessageBox.question(
                self,
                "Chip Image Discovery",
                "\n".join(summary_lines),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if result != QMessageBox.StandardButton.Yes:
                logger.info("User cancelled chip stitching")
                return
            
            # T048-T054: Proceed with chip stitching
            # Get stitching configuration
            dialog = StitchDialog(parent=self)
            if dialog.exec() != StitchDialog.DialogCode.Accepted:
                logger.info("User cancelled stitching configuration")
                return
            
            config = dialog.get_config()
            logger.info(f"Chip stitching config: alignment={config.alignment_method}, blend={config.blend_mode}")
            
            # T051: Create progress dialog
            self.chip_progress_dialog = QProgressDialog(
                "Preparing to stitch chip images...",
                "Cancel",
                0,
                100,
                self
            )
            self.chip_progress_dialog.setWindowTitle("Chip Stitching Progress")
            self.chip_progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.chip_progress_dialog.setMinimumDuration(0)
            self.chip_progress_dialog.setValue(0)
            
            # T050: Create and start chip stitching thread
            self.chip_stitching_thread = ChipStitchingThread(
                chip_set,
                self.alignment_parameters,
                config
            )
            
            # T052: Connect progress signals
            self.chip_stitching_thread.progress_updated.connect(self._handle_chip_stitching_progress)
            self.chip_stitching_thread.finished.connect(self._handle_chip_stitching_complete)
            self.chip_stitching_thread.error.connect(self._handle_chip_stitching_error)
            
            # Start stitching
            self.chip_stitching_thread.start()
            logger.info("Chip stitching thread started")
        
        except ChipImageNotFoundError as e:
            # This exception is no longer raised, but keep handler for backward compatibility
            logger.error(f"Chip image discovery error: {e}")
            QMessageBox.critical(
                self,
                "Chip Discovery Error",
                f"Error during chip image discovery:\n\n{str(e)}\n\n"
                "Please check the log for details.",
                QMessageBox.StandardButton.Ok
            )
        
        except Exception as e:
            logger.exception("Error during chip image discovery")
            QMessageBox.critical(
                self,
                "Discovery Error",
                f"An error occurred while discovering chip images:\n\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def _handle_chip_stitching_progress(self, percent: int, message: str):
        """Handle chip stitching progress updates (T052)."""
        try:
            if self.chip_progress_dialog:
                self.chip_progress_dialog.setValue(percent)
                self.chip_progress_dialog.setLabelText(f"{message} ({percent}%)")
        except Exception as e:
            logger.exception("Error updating chip stitching progress")
    
    def _handle_chip_stitching_complete(self, result: StitchedResult):
        """Handle chip stitching completion (T053-T054)."""
        try:
            # Close progress dialog
            if self.chip_progress_dialog:
                self.chip_progress_dialog.close()
                self.chip_progress_dialog = None
            
            # Store result
            self.last_result = result
            
            logger.info(
                f"Chip stitching complete: {result.full_width}×{result.full_height}px, "
                f"found={result.chip_metadata.chip_images_found}, "
                f"placeholders={result.chip_metadata.placeholders_generated}"
            )
            
            # Update status bar
            self.status_bar.showMessage(
                f"Chip stitching complete! {result.full_width}×{result.full_height}px"
            )
            
            # T053: Show result window with chip metadata
            try:
                result_window = ResultWindow(result, parent=self)
                result_window.show()
            except Exception as e:
                logger.exception("Error creating result window")
                QMessageBox.warning(
                    self,
                    "Display Error",
                    f"Chip stitching succeeded but could not display result:\n{str(e)}",
                    QMessageBox.StandardButton.Ok
                )
                return
            
            # Show success message
            try:
                summary_lines = [
                    f"Successfully stitched chip images!",
                    f"",
                    f"Resolution: {result.full_width} × {result.full_height} pixels",
                    f"Chip images found: {result.chip_metadata.chip_images_found}",
                    f"Placeholders generated: {result.chip_metadata.placeholders_generated}",
                    f"Processing time: {result.processing_time_seconds:.2f} seconds",
                ]
                
                if result.chip_metadata.dimension_transformations:
                    resized_count = sum(1 for t in result.chip_metadata.dimension_transformations if t.was_resized)
                    if resized_count > 0:
                        summary_lines.append(f"Images resized: {resized_count}")
                
                QMessageBox.information(
                    self,
                    "Chip Stitching Complete",
                    "\n".join(summary_lines),
                    QMessageBox.StandardButton.Ok
                )
            except Exception as e:
                logger.exception("Error showing success message")
                QMessageBox.information(
                    self,
                    "Chip Stitching Complete",
                    "Chip image stitching completed successfully!",
                    QMessageBox.StandardButton.Ok
                )
        
        except Exception as e:
            logger.exception("Critical error in chip stitching completion handler")
            if self.chip_progress_dialog:
                try:
                    self.chip_progress_dialog.close()
                    self.chip_progress_dialog = None
                except:
                    pass
    
    def _handle_chip_stitching_error(self, error_message: str):
        """Handle chip stitching errors (T054)."""
        try:
            # Close progress dialog
            if self.chip_progress_dialog:
                self.chip_progress_dialog.close()
                self.chip_progress_dialog = None
            
            logger.error(f"Chip stitching error: {error_message}")
            
            # Update status bar
            self.status_bar.showMessage("Chip stitching failed")
            
            # Show error dialog
            QMessageBox.critical(
                self,
                "Chip Stitching Failed",
                f"Chip stitching encountered an error:\n\n{error_message}\n\n"
                "Please check the log for details.",
                QMessageBox.StandardButton.Ok
            )
        
        except Exception as e:
            logger.exception("Critical error in chip stitching error handler")
            # Fallback error message
            try:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Chip stitching failed: {error_message}",
                    QMessageBox.StandardButton.Ok
                )
            except:
                pass
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Terminate stitching threads if running
        if self.stitching_thread and self.stitching_thread.isRunning():
            self.stitching_thread.terminate()
            self.stitching_thread.wait()
        
        if self.chip_stitching_thread and self.chip_stitching_thread.isRunning():
            self.chip_stitching_thread.terminate()
            self.chip_stitching_thread.wait()
        
        logger.info("MainWindow closing")
        event.accept()

