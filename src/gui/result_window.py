"""
ResultWindow - Stitched Image Display
Window for displaying stitched results with quality metrics
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsView, QGraphicsScene, QFileDialog, QGroupBox, QFormLayout,
    QGridLayout, QSpinBox, QComboBox
)
import cv2
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage, QPainter

from src.models import StitchedResult
from src.lib import io

logger = logging.getLogger(__name__)


class ResultWindow(QWidget):
    """
    Window for displaying stitched image with quality metrics.
    
    Features:
    - Large graphics view for stitched image
    - Quality metrics display (confidence, matches, warnings)
    - Resolution information
    - Save As functionality
    """
    
    def __init__(self, result: StitchedResult, parent: Optional[QWidget] = None):
        """
        Initialize result window.
        
        Args:
            result: StitchedResult with image data and metrics
            parent: Parent widget
        """
        super().__init__(parent)
        logger.info("ResultWindow.__init__ started")
        
        self.result = result
        
        try:
            self._setup_ui()
            logger.info("ResultWindow._setup_ui completed")
        except Exception as e:
            logger.exception(f"Error in _setup_ui: {e}")
            raise
        
        try:
            self._display_result()
            logger.info("ResultWindow._display_result completed")
        except Exception as e:
            logger.exception(f"Error in _display_result: {e}")
            raise
    
    def _setup_ui(self):
        """Set up window layout and components."""
        logger.info("_setup_ui: Setting window title and size")
        self.setWindowTitle("Stitching Result - NSEW Image Stitcher")
        self.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Title
        title = QLabel("<h2>✨ Stitching Complete!</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2e7d32; padding: 8px;")
        layout.addWidget(title)
        
        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)
        
        # Left: Image display
        image_group = QGroupBox("Stitched Image")
        image_layout = QVBoxLayout()
        
        self.graphics_view = QGraphicsView()
        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.graphics_view.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #4caf50;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        
        image_layout.addWidget(self.graphics_view)
        
        # Manual adjustment controls (for chip stitching results)
        adjust_group = QGroupBox("Manual Adjustments")
        adjust_layout = QGridLayout()
        adjust_layout.setSpacing(4)
        
        # Initialize per-quadrant adjustment values
        # Format: {quadrant: {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0}}
        # zoom is in percent: -5 to +5 (representing 95% to 105% scale)
        self._quadrant_adjustments = {
            'All': {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0},
            'NW': {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0},
            'NE': {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0},
            'SW': {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0},
            'SE': {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0},
        }
        
        # Store original quadrant images for re-compositing
        self._original_quadrant_images = {}
        
        # First try from source_quadrants (original stitch)
        logger.info(f"_setup_ui: Loading source_quadrants, count={len(self.result.source_quadrants) if self.result.source_quadrants else 0}")
        for q_img in (self.result.source_quadrants or []):
            if q_img.quadrant and q_img.image_data is not None:
                self._original_quadrant_images[q_img.quadrant.value] = q_img.image_data.copy()
                logger.info(f"Stored original image for {q_img.quadrant.value}: shape={q_img.image_data.shape}")
        
        # If no images from source_quadrants, try to load from alignment parameters
        if not self._original_quadrant_images and self.result.alignment_parameters:
            logger.info("Loading quadrant images from alignment parameters paths")
            for qa in self.result.alignment_parameters.quadrants:
                if qa.quadrant.value in self._original_quadrant_images:
                    continue  # Already have this one
                try:
                    orig_path = Path(qa.original_image_path)
                    
                    # For chip stitch, find the chip image
                    if self.result.is_chip_stitch:
                        chip_path = self._find_chip_image_for_quadrant(orig_path, qa.quadrant.value)
                        if chip_path and chip_path.exists():
                            img_data, _ = io.load_image(chip_path)
                            self._original_quadrant_images[qa.quadrant.value] = img_data
                            logger.info(f"Loaded chip image for {qa.quadrant.value}: {chip_path.name}, shape={img_data.shape}")
                    else:
                        # For original stitch, load from original path
                        if orig_path.exists():
                            img_data, _ = io.load_image(orig_path)
                            self._original_quadrant_images[qa.quadrant.value] = img_data
                            logger.info(f"Loaded original image for {qa.quadrant.value}: {orig_path.name}, shape={img_data.shape}")
                except Exception as e:
                    logger.warning(f"Could not load image for {qa.quadrant.value}: {e}")
        
        logger.info(f"Original quadrant images stored: {list(self._original_quadrant_images.keys())}")
        logger.info(f"Alignment parameters available: {self.result.alignment_parameters is not None}")
        
        # Quadrant selector
        quad_label = QLabel("Quadrant:")
        adjust_layout.addWidget(quad_label, 0, 0)
        
        self.quadrant_combo = QComboBox()
        self.quadrant_combo.addItems(['All', 'NW', 'NE', 'SW', 'SE'])
        self.quadrant_combo.setToolTip("Select which quadrant to adjust")
        self.quadrant_combo.currentTextChanged.connect(self._on_quadrant_changed)
        adjust_layout.addWidget(self.quadrant_combo, 0, 1)
        
        # Step size controls
        step_label = QLabel("Step:")
        adjust_layout.addWidget(step_label, 0, 2)
        
        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 100)
        self.step_spin.setValue(1)
        self.step_spin.setSuffix(" px")
        self.step_spin.setToolTip("Step size for X/Y shifts")
        adjust_layout.addWidget(self.step_spin, 0, 3)
        
        rot_step_label = QLabel("Rot:")
        adjust_layout.addWidget(rot_step_label, 0, 4)
        
        self.rot_step_spin = QSpinBox()
        self.rot_step_spin.setRange(1, 10)
        self.rot_step_spin.setValue(1)
        self.rot_step_spin.setSuffix("°")
        self.rot_step_spin.setToolTip("Step size for rotation")
        adjust_layout.addWidget(self.rot_step_spin, 0, 5)
        
        # X adjustment buttons
        self.x_minus_btn = QPushButton("X−")
        self.x_minus_btn.setToolTip("Shift left")
        self.x_minus_btn.clicked.connect(lambda: self._adjust_image('x', -1))
        adjust_layout.addWidget(self.x_minus_btn, 1, 0)
        
        self.x_plus_btn = QPushButton("X+")
        self.x_plus_btn.setToolTip("Shift right")
        self.x_plus_btn.clicked.connect(lambda: self._adjust_image('x', 1))
        adjust_layout.addWidget(self.x_plus_btn, 1, 1)
        
        # Y adjustment buttons
        self.y_minus_btn = QPushButton("Y−")
        self.y_minus_btn.setToolTip("Shift up")
        self.y_minus_btn.clicked.connect(lambda: self._adjust_image('y', -1))
        adjust_layout.addWidget(self.y_minus_btn, 1, 2)
        
        self.y_plus_btn = QPushButton("Y+")
        self.y_plus_btn.setToolTip("Shift down")
        self.y_plus_btn.clicked.connect(lambda: self._adjust_image('y', 1))
        adjust_layout.addWidget(self.y_plus_btn, 1, 3)
        
        # Rotation adjustment buttons
        self.rot_minus_btn = QPushButton("↺−")
        self.rot_minus_btn.setToolTip("Rotate counter-clockwise")
        self.rot_minus_btn.clicked.connect(lambda: self._adjust_image('rot', -1))
        adjust_layout.addWidget(self.rot_minus_btn, 1, 4)
        
        self.rot_plus_btn = QPushButton("↻+")
        self.rot_plus_btn.setToolTip("Rotate clockwise")
        self.rot_plus_btn.clicked.connect(lambda: self._adjust_image('rot', 1))
        adjust_layout.addWidget(self.rot_plus_btn, 1, 5)
        
        # Zoom step control and buttons (Row 2)
        zoom_step_label = QLabel("Zoom:")
        adjust_layout.addWidget(zoom_step_label, 2, 0)
        
        self.zoom_step_spin = QSpinBox()
        self.zoom_step_spin.setRange(1, 5)
        self.zoom_step_spin.setValue(1)
        self.zoom_step_spin.setSuffix("%")
        self.zoom_step_spin.setToolTip("Step size for zoom (±5% max)")
        adjust_layout.addWidget(self.zoom_step_spin, 2, 1)
        
        self.zoom_minus_btn = QPushButton("Z−")
        self.zoom_minus_btn.setToolTip("Zoom out (shrink)")
        self.zoom_minus_btn.clicked.connect(lambda: self._adjust_image('zoom', -1))
        adjust_layout.addWidget(self.zoom_minus_btn, 2, 2)
        
        self.zoom_plus_btn = QPushButton("Z+")
        self.zoom_plus_btn.setToolTip("Zoom in (enlarge)")
        self.zoom_plus_btn.clicked.connect(lambda: self._adjust_image('zoom', 1))
        adjust_layout.addWidget(self.zoom_plus_btn, 2, 3)
        
        # Reset button
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setToolTip("Reset adjustments for selected quadrant")
        self.reset_btn.clicked.connect(self._reset_adjustments)
        adjust_layout.addWidget(self.reset_btn, 2, 4)
        
        # Reset All button
        self.reset_all_btn = QPushButton("Reset All")
        self.reset_all_btn.setToolTip("Reset all quadrant adjustments")
        self.reset_all_btn.clicked.connect(self._reset_all_adjustments)
        adjust_layout.addWidget(self.reset_all_btn, 2, 5)
        
        # Current adjustment display (Row 3)
        self.adjust_status = QLabel("dx:0 dy:0 rot:0° zoom:0%")
        self.adjust_status.setStyleSheet("font-size: 10px; color: #666;")
        adjust_layout.addWidget(self.adjust_status, 3, 0, 1, 6)
        
        # Save corrected config button
        self.save_config_btn = QPushButton("💾 Save Config")
        self.save_config_btn.setToolTip("Save corrected alignment parameters to JSON")
        self.save_config_btn.clicked.connect(self._save_corrected_config)
        self.save_config_btn.setStyleSheet("background-color: #2196f3; color: white;")
        adjust_layout.addWidget(self.save_config_btn, 4, 0, 1, 3)
        
        # Regenerate original button
        self.regenerate_btn = QPushButton("🔄 Regenerate Original")
        self.regenerate_btn.setToolTip("Re-stitch original images with corrected parameters")
        self.regenerate_btn.clicked.connect(self._regenerate_original_images)
        self.regenerate_btn.setStyleSheet("background-color: #4caf50; color: white;")
        adjust_layout.addWidget(self.regenerate_btn, 4, 3, 1, 3)
        
        # Update original config button - saves to the alignment params file used for chip stitching
        self.update_config_btn = QPushButton("📝 Update Config for Chip Stitch")
        self.update_config_btn.setToolTip("Update the alignment parameters file so chip stitching uses corrected values")
        self.update_config_btn.clicked.connect(self._update_original_config)
        self.update_config_btn.setStyleSheet("background-color: #ff9800; color: white;")
        adjust_layout.addWidget(self.update_config_btn, 5, 0, 1, 6)
        
        adjust_group.setLayout(adjust_layout)
        adjust_group.setStyleSheet("""
            QGroupBox {
                font-size: 11px;
                padding-top: 12px;
            }
            QPushButton {
                padding: 4px 8px;
                font-weight: bold;
            }
        """)
        image_layout.addWidget(adjust_group)
        
        image_group.setLayout(image_layout)
        content_layout.addWidget(image_group, stretch=3)
        
        # Right: Metrics and info
        info_widget = QWidget()
        info_widget.setMaximumWidth(350)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(12)
        
        # Quality metrics group
        metrics_group = QGroupBox("Quality Metrics")
        metrics_layout = QFormLayout()
        metrics_layout.setSpacing(8)
        
        # Overall confidence
        self.confidence_label = QLabel()
        metrics_layout.addRow("Overall Quality:", self.confidence_label)
        
        # Feature matches
        self.matches_label = QLabel()
        metrics_layout.addRow("Feature Matches:", self.matches_label)
        
        # Inlier ratio
        self.inlier_label = QLabel()
        metrics_layout.addRow("Inlier Ratio:", self.inlier_label)
        
        # Processing time
        self.time_label = QLabel()
        metrics_layout.addRow("Processing Time:", self.time_label)
        
        metrics_group.setLayout(metrics_layout)
        info_layout.addWidget(metrics_group)
        
        # Resolution info group
        resolution_group = QGroupBox("Resolution")
        resolution_layout = QFormLayout()
        resolution_layout.setSpacing(8)
        
        self.full_res_label = QLabel()
        resolution_layout.addRow("Full Resolution:", self.full_res_label)
        
        self.display_res_label = QLabel()
        resolution_layout.addRow("Display Resolution:", self.display_res_label)
        
        self.downsampled_label = QLabel()
        resolution_layout.addRow("", self.downsampled_label)
        
        resolution_group.setLayout(resolution_layout)
        info_layout.addWidget(resolution_group)
        
        # Configuration info group
        config_group = QGroupBox("Configuration")
        config_layout = QFormLayout()
        config_layout.setSpacing(6)
        
        self.alignment_label = QLabel()
        config_layout.addRow("Alignment:", self.alignment_label)
        
        self.blend_label = QLabel()
        config_layout.addRow("Blend Mode:", self.blend_label)
        
        self.overlap_label = QLabel()
        config_layout.addRow("Overlap:", self.overlap_label)
        
        # Rotation information (if alignment parameters available)
        if self.result.alignment_parameters:
            self.rotation_label = QLabel()
            config_layout.addRow("Max Rotation:", self.rotation_label)
        
        config_group.setLayout(config_layout)
        info_layout.addWidget(config_group)
        
        # Alignment details group (rotation angles per quadrant)
        if self.result.alignment_parameters and self.result.alignment_parameters.quadrants:
            alignment_group = QGroupBox("Alignment Details")
            alignment_layout = QFormLayout()
            alignment_layout.setSpacing(6)
            
            # Display rotation angles for each quadrant
            for qa in self.result.alignment_parameters.quadrants:
                rotation_deg = getattr(qa, 'rotation_degrees', 0.0)
                if abs(rotation_deg) > 0.01:  # Only show non-zero rotations
                    rotation_text = f"{rotation_deg:.2f}°"
                    if abs(rotation_deg) > self.result.stitching_config.max_rotation_degrees:
                        rotation_text += " ⚠️"
                    rotation_label = QLabel(rotation_text)
                    if abs(rotation_deg) > self.result.stitching_config.max_rotation_degrees:
                        rotation_label.setStyleSheet("color: #ff6f00;")
                    alignment_layout.addRow(f"{qa.quadrant.value} Rotation:", rotation_label)
            
            alignment_group.setLayout(alignment_layout)
            info_layout.addWidget(alignment_group)
        
        # T055-T057: Chip metadata (if chip stitching result)
        if self.result.is_chip_stitch and self.result.chip_metadata:
            chip_group = QGroupBox("🔬 Chip Image Details")
            chip_layout = QFormLayout()
            chip_layout.setSpacing(6)
            
            # T056: Basic chip metadata
            self.chip_found_label = QLabel()
            chip_layout.addRow("Chip Images Found:", self.chip_found_label)
            
            self.chip_placeholders_label = QLabel()
            chip_layout.addRow("Placeholders Generated:", self.chip_placeholders_label)
            
            # Show which quadrants had placeholders
            if self.result.chip_metadata.placeholder_quadrants:
                placeholder_names = ", ".join([q.value for q in self.result.chip_metadata.placeholder_quadrants])
                placeholder_info = QLabel(f"({placeholder_names})")
                placeholder_info.setStyleSheet("color: #666; font-size: 9px;")
                placeholder_info.setWordWrap(True)
                chip_layout.addRow("", placeholder_info)
            
            # T057: Dimension transformation display
            if self.result.chip_metadata.dimension_transformations:
                resized_count = sum(1 for t in self.result.chip_metadata.dimension_transformations if t.was_resized)
                self.chip_resized_label = QLabel(f"{resized_count} image(s)")
                chip_layout.addRow("Dimensions Resized:", self.chip_resized_label)
                
                # Show which quadrants were resized with details
                if resized_count > 0:
                    resize_details = []
                    for transform in self.result.chip_metadata.dimension_transformations:
                        if transform.was_resized:
                            resize_details.append(
                                f"{transform.quadrant.value}: "
                                f"{transform.original_dimensions[0]}×{transform.original_dimensions[1]} → "
                                f"{transform.final_dimensions[0]}×{transform.final_dimensions[1]}"
                            )
                    
                    resize_info = QLabel("\n".join(resize_details))
                    resize_info.setStyleSheet("color: #666; font-size: 9px;")
                    resize_info.setWordWrap(True)
                    chip_layout.addRow("", resize_info)
            
            self.chip_time_label = QLabel()
            chip_layout.addRow("Chip Processing Time:", self.chip_time_label)
            
            chip_group.setLayout(chip_layout)
            chip_group.setStyleSheet("""
                QGroupBox {
                    border: 2px solid #2196f3;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px;
                    color: #2196f3;
                    font-weight: bold;
                }
            """)
            info_layout.addWidget(chip_group)
        
        # Warnings (if any)
        if self.result.quality_metrics.has_warnings():
            warnings_group = QGroupBox("⚠️ Warnings")
            warnings_layout = QVBoxLayout()
            
            for warning in self.result.quality_metrics.warnings:
                warning_label = QLabel(f"• {warning}")
                warning_label.setWordWrap(True)
                warning_label.setStyleSheet("color: #ff6f00; font-size: 9px;")
                warnings_layout.addWidget(warning_label)
            
            warnings_group.setLayout(warnings_layout)
            warnings_group.setStyleSheet("""
                QGroupBox {
                    border: 2px solid #ff6f00;
                    border-radius: 4px;
                    margin-top: 8px;
                    padding-top: 8px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px;
                }
            """)
            info_layout.addWidget(warnings_group)
        
        info_layout.addStretch()
        
        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)
        
        self.save_button = QPushButton("💾 Save As...")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.save_button.clicked.connect(self._on_save_clicked)
        button_layout.addWidget(self.save_button)
        
        close_button = QPushButton("Close")
        close_button.setStyleSheet("padding: 8px;")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        info_layout.addLayout(button_layout)
        
        content_layout.addWidget(info_widget)
        
        layout.addLayout(content_layout)
    
    def _display_result(self):
        """Display stitched image and populate metrics."""
        # Display image
        if self.result.stitched_image_data is not None:
            pixmap = self._numpy_to_qpixmap(self.result.stitched_image_data)
            self.scene.addPixmap(pixmap)
            self.graphics_view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        
        # Populate metrics
        metrics = self.result.quality_metrics
        
        # Confidence with color coding
        confidence = metrics.overall_confidence
        category = metrics.quality_category()
        if confidence >= 0.8:
            color = "#4caf50"  # Green
            icon = "✅"
        elif confidence >= 0.6:
            color = "#ff9800"  # Orange
            icon = "⚠️"
        else:
            color = "#f44336"  # Red
            icon = "❌"
        
        self.confidence_label.setText(
            f"<span style='color: {color}; font-weight: bold;'>{icon} {confidence:.2f}</span> "
            f"({category})"
        )
        
        self.matches_label.setText(str(metrics.feature_matches_total))
        self.inlier_label.setText(f"{metrics.inlier_ratio:.2f}")
        self.time_label.setText(f"{self.result.processing_time_seconds:.2f}s")
        
        # Resolution info
        self.full_res_label.setText(
            f"{self.result.full_width} × {self.result.full_height} px"
        )
        self.display_res_label.setText(
            f"{self.result.display_width} × {self.result.display_height} px"
        )
        
        if self.result.was_downsampled:
            self.downsampled_label.setText(
                "<span style='color: #2196f3;'>ℹ️ Full resolution saved to disk</span>"
            )
            self.downsampled_label.setWordWrap(True)
        
        # Configuration
        self.alignment_label.setText(self.result.stitching_config.alignment_method.upper())
        self.blend_label.setText(self.result.stitching_config.blend_mode.title())
        self.overlap_label.setText(
            f"{self.result.stitching_config.overlap_threshold_percent:.0f}%"
        )
        
        # Rotation information
        if hasattr(self, 'rotation_label'):
            self.rotation_label.setText(f"±{self.result.stitching_config.max_rotation_degrees:.1f}°")
        
        # T056-T057: Populate chip metadata (if chip stitching result)
        if self.result.is_chip_stitch and self.result.chip_metadata:
            chip_meta = self.result.chip_metadata
            
            # Found vs total
            total_quadrants = chip_meta.chip_images_found + chip_meta.placeholders_generated
            self.chip_found_label.setText(
                f"<span style='font-weight: bold;'>{chip_meta.chip_images_found}</span> of {total_quadrants}"
            )
            
            # Placeholders
            if chip_meta.placeholders_generated > 0:
                self.chip_placeholders_label.setText(
                    f"<span style='color: #ff9800; font-weight: bold;'>{chip_meta.placeholders_generated}</span>"
                )
            else:
                self.chip_placeholders_label.setText(
                    f"<span style='color: #4caf50;'>0 (all chips found!)</span>"
                )
            
            # Processing time
            self.chip_time_label.setText(f"{chip_meta.processing_time_seconds:.2f}s")
    
    def _numpy_to_qpixmap(self, image_data: np.ndarray) -> QPixmap:
        """Convert NumPy array to QPixmap."""
        # Normalize to uint8 if needed
        if image_data.dtype != np.uint8:
            img_min = image_data.min()
            img_max = image_data.max()
            if img_max > img_min:
                image_data = ((image_data - img_min) / (img_max - img_min) * 255).astype(np.uint8)
            else:
                image_data = np.zeros_like(image_data, dtype=np.uint8)
        
        height, width = image_data.shape[:2]
        
        if image_data.ndim == 2:
            image_data = np.ascontiguousarray(image_data)
            bytes_per_line = width
            qimage = QImage(
                bytes(image_data.data),
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_Grayscale8
            )
        elif image_data.ndim == 3 and image_data.shape[2] == 3:
            image_data = np.ascontiguousarray(image_data)
            bytes_per_line = 3 * width
            qimage = QImage(
                bytes(image_data.data),
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )
        elif image_data.ndim == 3 and image_data.shape[2] == 4:
            # RGBA image - use Format_RGBA8888
            image_data = np.ascontiguousarray(image_data)
            bytes_per_line = 4 * width
            qimage = QImage(
                bytes(image_data.data),
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGBA8888
            )
        else:
            # Fallback to first channel
            image_data = image_data[:, :, 0] if image_data.ndim == 3 else image_data
            image_data = np.ascontiguousarray(image_data)
            bytes_per_line = width
            qimage = QImage(
                bytes(image_data.data),
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_Grayscale8
            )
        
        qimage = qimage.copy()
        return QPixmap.fromImage(qimage)
    
    def _on_save_clicked(self):
        """Handle Save As button click - saves both mean-blended and overlay versions."""
        # Build default filename from prefix + ("original" | "chip")
        # Prefix is the CZI filename without the quadrant suffix (NE/NW/SE/SW)
        def _extract_prefix() -> str:
            try:
                # Prefer alignment parameters' original image paths
                if getattr(self.result, "alignment_parameters", None) and self.result.alignment_parameters.quadrants:
                    orig_path = self.result.alignment_parameters.quadrants[0].original_image_path
                    stem = Path(orig_path).stem
                elif self.result.source_quadrants:
                    stem = Path(self.result.source_quadrants[0].file_path).stem
                else:
                    return "stitched"
                quad_tags = {"NE", "NW", "SE", "SW"}
                if len(stem) >= 2 and stem[-2:].upper() in quad_tags:
                    return stem[:-2]
                return stem
            except Exception:
                return "stitched"
        
        from pathlib import Path
        prefix = _extract_prefix()
        tag = "chip" if getattr(self.result, "is_chip_stitch", False) else "original"
        # Map output format to extension
        ext_map = {"tiff": ".tiff", "png": ".png", "jpeg": ".jpg"}
        ext = ext_map.get(self.result.stitching_config.output_format, ".tiff")
        default_name = f"{prefix}{tag}{ext}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stitched Image",
            default_name,
            "TIFF Image (*.tif *.tiff);;PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*)"
        )
        
        if file_path:
            try:
                # Determine which image to save based on stitch type
                image_to_save = getattr(self, '_adjusted_image_data', None)
                
                if self.result.is_chip_stitch:
                    # For chip stitch: use stitched_image_data directly (already computed with correct bounds)
                    # Don't regenerate - that would use original cell images instead of chip images!
                    if image_to_save is None:
                        image_to_save = self.result.stitched_image_data
                    logger.info(f"Using chip stitch result: shape={image_to_save.shape}")
                else:
                    # For original stitch: regenerate with computed bounds if needed
                    if image_to_save is None:
                        logger.info("Regenerating original images with computed bounds before saving...")
                        self._regenerate_original_images()
                        image_to_save = getattr(self, '_adjusted_image_data', None)
                    
                    if image_to_save is None:
                        # Fallback if regeneration failed
                        image_to_save = self.result.stitched_image_data
                        logger.info(f"Using original stitched_image_data (fallback): shape={image_to_save.shape}")
                    else:
                        logger.info(f"Using regenerated image_data: shape={image_to_save.shape}")
                
                # Parse the file path to create two versions
                file_path_obj = Path(file_path)
                stem = file_path_obj.stem
                suffix = file_path_obj.suffix
                parent = file_path_obj.parent
                
                # Save mean-blended version (current behavior)
                mean_path = parent / f"{stem}_mean{suffix}"
                io.save_image(
                    image_to_save,
                    mean_path,
                    format=self.result.stitching_config.output_format,
                    compression_level=self.result.stitching_config.compression_level
                )
                logger.info(f"Saved mean-blended image to {mean_path}")
                
                # Generate and save overlay version (NW, NE, SW, SE order - bottom to top)
                # Use exact same dimensions as mean image for consistency
                mean_dimensions = image_to_save.shape[:2]  # (height, width)
                overlay_image = self._generate_overlay_image(target_dimensions=mean_dimensions)
                if overlay_image is not None:
                    overlay_path = parent / f"{stem}_overlay{suffix}"
                    io.save_image(
                        overlay_image,
                        overlay_path,
                        format=self.result.stitching_config.output_format,
                        compression_level=self.result.stitching_config.compression_level
                    )
                    logger.info(f"Saved overlay image to {overlay_path}")
                
                self.save_button.setText("✅ Saved!")
                self.save_button.setEnabled(False)
                
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self,
                    "Images Saved",
                    f"Two versions saved:\n\n"
                    f"1. Mean-blended: {mean_path.name}\n"
                    f"2. Overlay: {stem}_overlay{suffix}",
                    QMessageBox.StandardButton.Ok
                )
            
            except Exception as e:
                logger.exception(f"Failed to save image: {e}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self,
                    "Save Failed",
                    f"Could not save image:\n{str(e)}",
                    QMessageBox.StandardButton.Ok
                )
    
    def _generate_overlay_image(self, target_dimensions: tuple = None) -> Optional[np.ndarray]:
        """
        Generate an overlay version of the stitched image.
        Overlays quadrants in order: NW (bottom), NE, SW, SE (top).
        No blending - later quadrants simply overwrite earlier ones.
        
        Args:
            target_dimensions: Optional (height, width) tuple to force exact canvas size
        """
        if not self._original_quadrant_images or not self.result.alignment_parameters:
            logger.warning("Cannot generate overlay: missing quadrant images or alignment params")
            return None
        
        # Get base alignment parameters
        base_params = self._get_base_alignment_params()
        if not base_params:
            return None
        
        # Get origin offset
        ox, oy = 0.0, 0.0
        if self.result.alignment_parameters.origin_offset:
            ox, oy = self.result.alignment_parameters.origin_offset
        
        # Calculate adjusted parameters for each quadrant (including manual adjustments)
        adjusted_params = {}
        for quad_name in ['NW', 'NE', 'SW', 'SE']:
            if quad_name in base_params:
                base = base_params[quad_name]
                adj = self._quadrant_adjustments[quad_name]
                adjusted_params[quad_name] = {
                    'dx': base['dx'] + adj['dx'],
                    'dy': base['dy'] + adj['dy'],
                    'rot': base['rot'] + adj['rot'],
                    'zoom': adj.get('zoom', 0.0),
                    'w': base['w'],
                    'h': base['h']
                }
        
        # ALWAYS compute canvas bounds to get the correct offset
        # The offset calculation depends on quadrant positions and must be consistent
        computed_w, computed_h, ox, oy = self._compute_canvas_bounds_with_rotation(adjusted_params, ox, oy)
        
        # Use target dimensions if provided (to match mean image exactly)
        if target_dimensions is not None:
            canvas_h, canvas_w = target_dimensions
            logger.debug(f"_generate_overlay: using target_dimensions {canvas_w}x{canvas_h}, computed offset: ({ox}, {oy})")
        else:
            canvas_w, canvas_h = computed_w, computed_h
            logger.debug(f"_generate_overlay: computed bounds {canvas_w}x{canvas_h}, offset: ({ox}, {oy})")
        
        # Create canvas (RGBA)
        canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
        
        # Overlay each quadrant in order: NW, NE, SW, SE (bottom to top)
        for quad_name in ['NW', 'NE', 'SW', 'SE']:
            if quad_name not in self._original_quadrant_images:
                continue
            if quad_name not in adjusted_params:
                continue
            
            img = self._original_quadrant_images[quad_name].copy()
            p = adjusted_params[quad_name]
            
            # Convert to uint8 if needed
            if img.dtype == np.uint16:
                img_min, img_max = img.min(), img.max()
                if img_max > img_min:
                    img = ((img - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                else:
                    img = np.zeros_like(img, dtype=np.uint8)
            
            # Convert to RGBA
            if img.ndim == 2:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, 0] = img
                rgba[:, :, 1] = img
                rgba[:, :, 2] = img
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 1:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, 0] = img[:, :, 0]
                rgba[:, :, 1] = img[:, :, 0]
                rgba[:, :, 2] = img[:, :, 0]
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 3:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, :3] = img
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 4:
                img[:, :, 3] = 255
            
            h, w = img.shape[:2]
            rot = p['rot']
            zoom_percent = p.get('zoom', 0.0)
            scale = 1.0 + (zoom_percent / 100.0)
            
            # Apply zoom and rotation
            if abs(rot) > 0.01 or abs(zoom_percent) > 0.01:
                center = (w / 2.0, h / 2.0)
                rot_matrix = cv2.getRotationMatrix2D(center, -rot, scale)
                new_w = int(w * scale)
                new_h = int(h * scale)
                rot_matrix[0, 2] += (new_w - w) / 2
                rot_matrix[1, 2] += (new_h - h) / 2
                img = cv2.warpAffine(img, rot_matrix, (new_w, new_h), 
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
                h, w = img.shape[:2]
            
            # Calculate position on canvas
            x = int(p['dx'] + ox)
            y = int(p['dy'] + oy)
            
            # Clip to canvas bounds
            src_x0 = max(0, -x)
            src_y0 = max(0, -y)
            src_x1 = w - max(0, x + w - canvas_w)
            src_y1 = h - max(0, y + h - canvas_h)
            
            dst_x0 = max(0, x)
            dst_y0 = max(0, y)
            dst_x1 = min(canvas_w, x + w)
            dst_y1 = min(canvas_h, y + h)
            
            # Simple overlay: later quadrants overwrite earlier ones
            if dst_x1 > dst_x0 and dst_y1 > dst_y0 and src_x1 > src_x0 and src_y1 > src_y0:
                src_region = img[src_y0:src_y1, src_x0:src_x1]
                # Only overwrite where source has content (alpha > 0)
                mask = src_region[:, :, 3] > 0
                for c in range(4):
                    canvas[dst_y0:dst_y1, dst_x0:dst_x1, c] = np.where(
                        mask, src_region[:, :, c], canvas[dst_y0:dst_y1, dst_x0:dst_x1, c]
                    )
        
        # Apply "All" adjustments to the entire composited image (same as mean image)
        all_adj = self._quadrant_adjustments['All']
        total_dx = all_adj['dx']
        total_dy = all_adj['dy']
        total_rot = all_adj['rot']
        
        # Apply global rotation if non-zero
        if abs(total_rot) > 0.01:
            h, w = canvas.shape[:2]
            center = (w / 2.0, h / 2.0)
            rot_matrix = cv2.getRotationMatrix2D(center, -total_rot, 1.0)
            
            cos_val = abs(rot_matrix[0, 0])
            sin_val = abs(rot_matrix[0, 1])
            new_w = int(h * sin_val + w * cos_val)
            new_h = int(h * cos_val + w * sin_val)
            
            rot_matrix[0, 2] += (new_w - w) / 2
            rot_matrix[1, 2] += (new_h - h) / 2
            
            canvas = cv2.warpAffine(
                canvas, rot_matrix, (new_w, new_h),
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
            )
        
        # Apply global translation if non-zero
        if total_dx != 0 or total_dy != 0:
            h, w = canvas.shape[:2]
            trans_matrix = np.float32([[1, 0, total_dx], [0, 1, total_dy]])
            
            canvas = cv2.warpAffine(
                canvas, trans_matrix, (w, h),
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
            )
        
        return canvas
    
    def _find_chip_image_for_quadrant(self, original_path: Path, quadrant: str) -> Optional[Path]:
        """
        Find the chip image corresponding to an original quadrant image.
        
        Looks for chip images in the same directory with naming patterns like:
        - original: 2025.10.22-10.34.56-4134-opnT2_NW.czi
        - chip: 2025.10.22-10.34.56-4134-opnT2_NW_chip.tif or similar
        
        Args:
            original_path: Path to the original quadrant image
            quadrant: Quadrant name (NW, NE, SW, SE)
            
        Returns:
            Path to chip image if found, None otherwise
        """
        if not original_path.exists():
            # Try parent directory
            search_dir = original_path.parent
        else:
            search_dir = original_path.parent
        
        stem = original_path.stem
        
        # Look for chip image patterns
        patterns = [
            f"{stem}_chip.*",
            f"{stem}chip.*",
            f"{stem}*chip*",
        ]
        
        for pattern in patterns:
            matches = list(search_dir.glob(pattern))
            for match in matches:
                if match.suffix.lower() in ['.tif', '.tiff', '.png', '.jpg', '.jpeg']:
                    return match
        
        # Also try looking for files that contain the quadrant and "chip"
        for f in search_dir.iterdir():
            if f.is_file() and quadrant in f.stem and 'chip' in f.stem.lower():
                if f.suffix.lower() in ['.tif', '.tiff', '.png', '.jpg', '.jpeg', '.czi', '.lsm']:
                    return f
        
        return None
    
    def _on_quadrant_changed(self, quadrant: str):
        """Update status display when quadrant selection changes."""
        adj = self._quadrant_adjustments[quadrant]
        self.adjust_status.setText(f"dx:{adj['dx']} dy:{adj['dy']} rot:{adj['rot']}° zoom:{adj['zoom']}%")
    
    def _adjust_image(self, axis: str, direction: int):
        """
        Adjust the displayed image by shifting, rotating, or zooming.
        
        Args:
            axis: 'x', 'y', 'rot', or 'zoom'
            direction: +1 or -1
        """
        quadrant = self.quadrant_combo.currentText()
        adj = self._quadrant_adjustments[quadrant]
        
        if axis == 'x':
            step = self.step_spin.value()
            adj['dx'] += direction * step
        elif axis == 'y':
            step = self.step_spin.value()
            adj['dy'] += direction * step
        elif axis == 'rot':
            step = self.rot_step_spin.value()
            adj['rot'] += direction * step
        elif axis == 'zoom':
            step = self.zoom_step_spin.value()
            new_zoom = adj['zoom'] + direction * step
            # Clamp zoom to ±5%
            adj['zoom'] = max(-5, min(5, new_zoom))
        
        # Update status display
        self.adjust_status.setText(f"dx:{adj['dx']} dy:{adj['dy']} rot:{adj['rot']}° zoom:{adj['zoom']}%")
        
        # Apply adjustments and redisplay
        self._apply_adjustments_and_display()
    
    def _reset_adjustments(self):
        """Reset adjustments for selected quadrant."""
        quadrant = self.quadrant_combo.currentText()
        self._quadrant_adjustments[quadrant] = {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0}
        self.adjust_status.setText("dx:0 dy:0 rot:0° zoom:0%")
        self._apply_adjustments_and_display()
    
    def _reset_all_adjustments(self):
        """Reset all quadrant adjustments."""
        for q in self._quadrant_adjustments:
            self._quadrant_adjustments[q] = {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0}
        self.adjust_status.setText("dx:0 dy:0 rot:0° zoom:0%")
        self._apply_adjustments_and_display()
    
    def _get_base_alignment_params(self):
        """
        Get base alignment parameters for each quadrant.
        Returns dict: {quadrant_name: {'dx': float, 'dy': float, 'rot': float, 'w': int, 'h': int}}
        """
        params = {}
        if not self.result.alignment_parameters:
            return params
        
        for qa in self.result.alignment_parameters.quadrants:
            dx, dy = qa.position_shift
            w, h = qa.dimensions
            rot = qa.rotation_degrees
            params[qa.quadrant.value] = {'dx': dx, 'dy': dy, 'rot': rot, 'w': w, 'h': h}
        
        return params
    
    def _compute_canvas_bounds_with_rotation(self, adjusted_params: dict, ox: float, oy: float):
        """
        Compute canvas bounds accounting for rotation and zoom.
        Returns (canvas_w, canvas_h, offset_x, offset_y).
        """
        min_x, min_y = 0.0, 0.0
        max_x, max_y = 0.0, 0.0
        
        for quad_name, p in adjusted_params.items():
            w, h = p['w'], p['h']
            dx, dy = p['dx'], p['dy']
            rot = p['rot']
            zoom_percent = p.get('zoom', 0.0)
            scale = 1.0 + (zoom_percent / 100.0)
            
            if abs(rot) > 0.01 or abs(scale - 1.0) > 0.001:
                # Compute corners after rotation/scale
                angle_rad = np.radians(-rot)
                cos_a, sin_a = np.cos(angle_rad) * scale, np.sin(angle_rad) * scale
                cx, cy = w / 2.0, h / 2.0
                corners = [
                    (0 - cx, 0 - cy),
                    (w - cx, 0 - cy),
                    (w - cx, h - cy),
                    (0 - cx, h - cy)
                ]
                rotated = [(cos_a * x - sin_a * y + cx, sin_a * x + cos_a * y + cy) for x, y in corners]
                x_coords = [dx + rx for rx, ry in rotated]
                y_coords = [dy + ry for rx, ry in rotated]
                min_x = min(min_x, min(x_coords))
                min_y = min(min_y, min(y_coords))
                max_x = max(max_x, max(x_coords))
                max_y = max(max_y, max(y_coords))
            else:
                min_x = min(min_x, dx)
                min_y = min(min_y, dy)
                max_x = max(max_x, dx + w)
                max_y = max(max_y, dy + h)
        
        # Calculate canvas size from bounding box
        canvas_w = int(np.ceil(max_x - min_x))
        canvas_h = int(np.ceil(max_y - min_y))
        
        # Adjust origin offset if needed
        offset_x = ox + (-min_x if min_x < 0 else 0.0)
        offset_y = oy + (-min_y if min_y < 0 else 0.0)
        
        return canvas_w, canvas_h, offset_x, offset_y
    
    def _apply_adjustments_and_display(self):
        """Re-composite the image from original quadrant data with adjusted parameters."""
        
        logger.info(f"Applying adjustments. Original images: {list(self._original_quadrant_images.keys())}")
        logger.info(f"Adjustments: {self._quadrant_adjustments}")
        
        # Check if we have the original quadrant images
        if not self._original_quadrant_images or not self.result.alignment_parameters:
            logger.warning("No original images or alignment params - using fallback display")
            # Fallback: just show original stitched image
            pixmap = self._numpy_to_qpixmap(self.result.stitched_image_data)
            self.scene.clear()
            self.scene.addPixmap(pixmap)
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            self.graphics_view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            return
        
        # Get base alignment parameters
        base_params = self._get_base_alignment_params()
        
        # Get origin offset
        ox, oy = 0.0, 0.0
        if self.result.alignment_parameters.origin_offset:
            ox, oy = self.result.alignment_parameters.origin_offset
        
        # Calculate adjusted parameters for each quadrant
        adjusted_params = {}
        for quad_name in ['NW', 'NE', 'SW', 'SE']:
            if quad_name in base_params:
                base = base_params[quad_name]
                adj = self._quadrant_adjustments[quad_name]
                adjusted_params[quad_name] = {
                    'dx': base['dx'] + adj['dx'],
                    'dy': base['dy'] + adj['dy'],
                    'rot': base['rot'] + adj['rot'],
                    'zoom': adj.get('zoom', 0.0),  # Zoom in percent (-5 to +5)
                    'w': base['w'],
                    'h': base['h']
                }
        
        # ALWAYS compute canvas bounds from quadrant positions to ensure no pixels are clipped
        canvas_w, canvas_h, ox, oy = self._compute_canvas_bounds_with_rotation(adjusted_params, ox, oy)
        logger.info(f"_apply_adjustments_and_display: computed bounds: {canvas_w}x{canvas_h}")
        
        # Create canvas (RGBA for transparency) and accumulators for mean blending
        canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
        sum_canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.float64)
        count_canvas = np.zeros((canvas_h, canvas_w), dtype=np.int32)
        
        # Composite each quadrant onto the canvas
        for quad_name in ['NW', 'NE', 'SW', 'SE']:
            if quad_name not in self._original_quadrant_images:
                continue
            if quad_name not in adjusted_params:
                continue
            
            img = self._original_quadrant_images[quad_name].copy()
            p = adjusted_params[quad_name]
            
            # Convert to uint8 if needed
            if img.dtype == np.uint16:
                img_min, img_max = img.min(), img.max()
                if img_max > img_min:
                    img = ((img - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                else:
                    img = np.zeros_like(img, dtype=np.uint8)
            
            # Convert to RGBA
            if img.ndim == 2:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, 0] = img
                rgba[:, :, 1] = img
                rgba[:, :, 2] = img
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 1:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, 0] = img[:, :, 0]
                rgba[:, :, 1] = img[:, :, 0]
                rgba[:, :, 2] = img[:, :, 0]
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 3:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, :3] = img
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 4:
                img[:, :, 3] = 255  # Ensure opaque
            
            # Apply quadrant-specific color tint
            tints = {'NW': (25, 0, 0), 'NE': (0, 25, 0), 'SW': (0, 0, 25), 'SE': (20, 20, 0)}
            tint = tints.get(quad_name, (0, 0, 0))
            for c in range(3):
                if tint[c] > 0:
                    img[:, :, c] = np.clip(img[:, :, c].astype(np.int16) + tint[c], 0, 255).astype(np.uint8)
            
            h, w = img.shape[:2]
            rot = p['rot']
            zoom_percent = p.get('zoom', 0.0)
            
            # Calculate scale factor from zoom percent (e.g., -5% = 0.95, +5% = 1.05)
            scale = 1.0 + (zoom_percent / 100.0)
            
            # Apply zoom and rotation together using affine transformation
            if abs(rot) > 0.01 or abs(zoom_percent) > 0.01:
                center = (w / 2.0, h / 2.0)
                # Get rotation matrix with scale
                rot_matrix = cv2.getRotationMatrix2D(center, -rot, scale)
                
                # Calculate new dimensions after scaling
                new_w = int(w * scale)
                new_h = int(h * scale)
                
                # Adjust matrix for new center
                rot_matrix[0, 2] += (new_w - w) / 2
                rot_matrix[1, 2] += (new_h - h) / 2
                
                img = cv2.warpAffine(img, rot_matrix, (new_w, new_h), 
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
                h, w = img.shape[:2]  # Update dimensions
            
            # Calculate position on canvas
            x = int(p['dx'] + ox)
            y = int(p['dy'] + oy)
            
            # Clip to canvas bounds
            src_x0 = max(0, -x)
            src_y0 = max(0, -y)
            src_x1 = w - max(0, x + w - canvas_w)
            src_y1 = h - max(0, y + h - canvas_h)
            
            dst_x0 = max(0, x)
            dst_y0 = max(0, y)
            dst_x1 = min(canvas_w, x + w)
            dst_y1 = min(canvas_h, y + h)
            
            # Place on canvas using mean blending for overlapping regions
            if dst_x1 > dst_x0 and dst_y1 > dst_y0 and src_x1 > src_x0 and src_y1 > src_y0:
                src_region = img[src_y0:src_y1, src_x0:src_x1]
                
                # Create mask for pixels with content (alpha > 0)
                content_mask = src_region[:, :, 3] > 0
                
                # Accumulate RGB values and count for mean blending
                for c in range(3):
                    sum_canvas[dst_y0:dst_y1, dst_x0:dst_x1, c] += np.where(
                        content_mask, src_region[:, :, c].astype(np.float64), 0
                    )
                count_canvas[dst_y0:dst_y1, dst_x0:dst_x1] += content_mask.astype(np.int32)
        
        # Compute mean from accumulated values
        valid_mask = count_canvas > 0
        for c in range(3):
            canvas[:, :, c] = np.where(
                valid_mask,
                (sum_canvas[:, :, c] / np.maximum(count_canvas, 1)).astype(np.uint8),
                0
            )
        # Set alpha: semi-transparent for chip preview
        canvas[:, :, 3] = np.where(valid_mask, 200, 0)  # Slightly transparent for preview
        
        # Apply "All" adjustments to the entire composited image
        all_adj = self._quadrant_adjustments['All']
        total_dx = all_adj['dx']
        total_dy = all_adj['dy']
        total_rot = all_adj['rot']
        
        image_data = canvas
        
        # Apply global rotation if non-zero
        if abs(total_rot) > 0.01:
            h, w = image_data.shape[:2]
            center = (w / 2.0, h / 2.0)
            rot_matrix = cv2.getRotationMatrix2D(center, -total_rot, 1.0)
            
            cos_val = abs(rot_matrix[0, 0])
            sin_val = abs(rot_matrix[0, 1])
            new_w = int(h * sin_val + w * cos_val)
            new_h = int(h * cos_val + w * sin_val)
            
            rot_matrix[0, 2] += (new_w - w) / 2
            rot_matrix[1, 2] += (new_h - h) / 2
            
            image_data = cv2.warpAffine(
                image_data, rot_matrix, (new_w, new_h),
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
            )
        
        # Apply global translation if non-zero
        if total_dx != 0 or total_dy != 0:
            h, w = image_data.shape[:2]
            trans_matrix = np.float32([[1, 0, total_dx], [0, 1, total_dy]])
            
            image_data = cv2.warpAffine(
                image_data, trans_matrix, (w, h),
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
            )
        
        # Store adjusted image for saving
        self._adjusted_image_data = image_data
        
        # Convert to pixmap and display
        pixmap = self._numpy_to_qpixmap(image_data)
        
        self.scene.clear()
        self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.graphics_view.fitInView(
            self.scene.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio
        )
    
    def _get_corrected_alignment_params(self):
        """
        Build corrected alignment parameters with user adjustments applied.
        Returns a new AlignmentParameters object with updated position_shift and rotation.
        
        IMPORTANT: This includes both per-quadrant adjustments AND global "All" adjustments.
        The global adjustments are applied to each quadrant's translation/rotation.
        """
        from src.models.alignment_parameters import AlignmentParameters, QuadrantAlignment
        from datetime import datetime
        
        if not self.result.alignment_parameters:
            return None
        
        orig = self.result.alignment_parameters
        
        # Get global "All" adjustments
        all_adj = self._quadrant_adjustments.get('All', {'dx': 0, 'dy': 0, 'rot': 0.0})
        global_dx = all_adj['dx']
        global_dy = all_adj['dy']
        global_rot = all_adj['rot']
        
        logger.info(f"Including global adjustments: dx={global_dx}, dy={global_dy}, rot={global_rot}")
        
        # Create corrected quadrant alignments
        corrected_quadrants = []
        for qa in orig.quadrants:
            adj = self._quadrant_adjustments.get(qa.quadrant.value, {'dx': 0, 'dy': 0, 'rot': 0.0, 'zoom': 0.0})
            
            # Apply per-quadrant adjustments PLUS global adjustments
            new_dx = qa.position_shift[0] + adj['dx'] + global_dx
            new_dy = qa.position_shift[1] + adj['dy'] + global_dy
            new_rot = qa.rotation_degrees + adj['rot'] + global_rot
            new_zoom = qa.zoom_percent + adj.get('zoom', 0.0)
            
            corrected_qa = QuadrantAlignment(
                quadrant=qa.quadrant,
                original_image_path=qa.original_image_path,
                dimensions=qa.dimensions,
                position_shift=(new_dx, new_dy),
                rotation_degrees=new_rot,
                zoom_percent=new_zoom
            )
            corrected_quadrants.append(corrected_qa)
        
        # ALWAYS use regenerated image dimensions to ensure no pixels are clipped
        if hasattr(self, '_adjusted_image_data') and self._adjusted_image_data is not None:
            # Use the regenerated image dimensions (height, width from numpy shape)
            h, w = self._adjusted_image_data.shape[:2]
            new_final_dimensions = (w, h)  # (width, height)
            logger.info(f"Using regenerated image dimensions for corrected_params: {w}x{h}")
        else:
            # Fallback: keep original final_dimensions
            new_final_dimensions = orig.final_dimensions
            logger.info(f"Using original final_dimensions for corrected_params (fallback): {new_final_dimensions}")
        
        # Create new alignment parameters
        corrected_params = AlignmentParameters(
            version=orig.version,
            timestamp=datetime.now().isoformat(),
            stitched_image_path=orig.stitched_image_path,
            quadrants=corrected_quadrants,
            final_dimensions=new_final_dimensions,
            origin_offset=orig.origin_offset
        )
        
        return corrected_params
    
    def _save_corrected_config(self):
        """Save the corrected alignment parameters to a JSON file."""
        from src.models.alignment_parameters import to_dict
        import json
        from PyQt6.QtWidgets import QMessageBox
        
        corrected_params = self._get_corrected_alignment_params()
        if not corrected_params:
            QMessageBox.warning(
                self,
                "No Parameters",
                "No alignment parameters available to save.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Default filename
        default_name = ".image_mea_alignment_params_corrected.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Corrected Alignment Parameters",
            default_name,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                params_dict = to_dict(corrected_params)
                with open(file_path, 'w') as f:
                    json.dump(params_dict, f, indent=2)
                
                logger.info(f"Saved corrected alignment parameters to {file_path}")
                self.save_config_btn.setText("✅ Config Saved!")
                
                QMessageBox.information(
                    self,
                    "Config Saved",
                    f"Corrected alignment parameters saved to:\n{file_path}",
                    QMessageBox.StandardButton.Ok
                )
            except Exception as e:
                logger.exception(f"Failed to save config: {e}")
                QMessageBox.critical(
                    self,
                    "Save Failed",
                    f"Could not save configuration:\n{str(e)}",
                    QMessageBox.StandardButton.Ok
                )
    
    def _update_original_config(self):
        """
        Update the original alignment parameters file with corrected values.
        This allows chip stitching to use the manually corrected parameters.
        """
        from src.models.alignment_parameters import to_dict
        import json
        from PyQt6.QtWidgets import QMessageBox
        
        corrected_params = self._get_corrected_alignment_params()
        if not corrected_params:
            QMessageBox.warning(
                self,
                "No Parameters",
                "No alignment parameters available to update.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Find the original alignment parameters file
        # It's typically stored in the same directory as the stitched image
        original_config_path = None
        
        if self.result.alignment_parameters and self.result.alignment_parameters.stitched_image_path:
            stitched_path = Path(self.result.alignment_parameters.stitched_image_path)
            parent_dir = stitched_path.parent
            
            # Look for the alignment params file - common naming patterns
            possible_names = [
                ".image_mea_alignment_params.json",
                "image_mea_alignment_params.json",
                f"{stitched_path.stem}_alignment_params.json",
            ]
            
            for name in possible_names:
                candidate = parent_dir / name
                if candidate.exists():
                    original_config_path = candidate
                    break
            
            # If not found, also check the workspace root
            if not original_config_path:
                workspace_root = Path.cwd()
                for name in possible_names:
                    candidate = workspace_root / name
                    if candidate.exists():
                        original_config_path = candidate
                        break
        
        # If still not found, use default path
        if not original_config_path:
            if self.result.alignment_parameters and self.result.alignment_parameters.stitched_image_path:
                parent_dir = Path(self.result.alignment_parameters.stitched_image_path).parent
            else:
                parent_dir = Path.cwd()
            original_config_path = parent_dir / ".image_mea_alignment_params.json"
        
        # Confirm overwrite
        if original_config_path.exists():
            reply = QMessageBox.question(
                self,
                "Update Configuration",
                f"This will overwrite the alignment parameters file:\n\n"
                f"{original_config_path}\n\n"
                f"Chip stitching will use the corrected parameters.\n\n"
                f"Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        else:
            reply = QMessageBox.question(
                self,
                "Create Configuration",
                f"No existing alignment file found. Create new file at:\n\n"
                f"{original_config_path}\n\n"
                f"Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            params_dict = to_dict(corrected_params)
            with open(original_config_path, 'w') as f:
                json.dump(params_dict, f, indent=2)
            
            logger.info(f"Updated alignment parameters at {original_config_path}")
            self.update_config_btn.setText("✅ Config Updated!")
            
            QMessageBox.information(
                self,
                "Configuration Updated",
                f"Alignment parameters updated successfully!\n\n"
                f"File: {original_config_path}\n\n"
                f"Chip stitching will now use the corrected parameters.",
                QMessageBox.StandardButton.Ok
            )
        except Exception as e:
            logger.exception(f"Failed to update config: {e}")
            QMessageBox.critical(
                self,
                "Update Failed",
                f"Could not update configuration:\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def _regenerate_original_images(self):
        """Re-stitch original images with corrected alignment parameters."""
        from PyQt6.QtWidgets import QMessageBox, QProgressDialog
        from src.lib import stitching
        
        corrected_params = self._get_corrected_alignment_params()
        if not corrected_params:
            QMessageBox.warning(
                self,
                "No Parameters",
                "No alignment parameters available for regeneration.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Check if we have original image paths
        if not corrected_params.quadrants:
            QMessageBox.warning(
                self,
                "No Quadrants",
                "No quadrant information available.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # Confirm action
        reply = QMessageBox.question(
            self,
            "Regenerate Original Images",
            "This will re-stitch the original channel images using the corrected parameters.\n\n"
            "Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Show progress
            progress = QProgressDialog("Re-stitching original images...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            # Load original images
            quadrant_images = []
            from src.models import QuadrantImage, Quadrant
            
            for qa in corrected_params.quadrants:
                orig_path = Path(qa.original_image_path)
                if orig_path.exists():
                    img_data, metadata = io.load_image(orig_path)
                    q_img = QuadrantImage(
                        file_path=orig_path,
                        quadrant=qa.quadrant,
                        image_data=img_data,
                        dimensions=(img_data.shape[0], img_data.shape[1])
                    )
                    quadrant_images.append(q_img)
                    logger.info(f"Loaded original image: {orig_path.name}")
            
            if not quadrant_images:
                progress.close()
                QMessageBox.warning(
                    self,
                    "No Images",
                    "Could not find any original images to re-stitch.",
                    QMessageBox.StandardButton.Ok
                )
                return
            
            # Use corrected params for composition
            # Re-composite using the corrected alignment
            self._recomposite_with_corrected_params(quadrant_images, corrected_params)
            
            progress.close()
            
            QMessageBox.information(
                self,
                "Regeneration Complete",
                "Original images have been re-stitched with corrected parameters.\n\n"
                "Use 'Save As...' to save the result.",
                QMessageBox.StandardButton.Ok
            )
            
        except Exception as e:
            logger.exception(f"Failed to regenerate: {e}")
            QMessageBox.critical(
                self,
                "Regeneration Failed",
                f"Could not regenerate images:\n{str(e)}",
                QMessageBox.StandardButton.Ok
            )
    
    def _recomposite_with_corrected_params(self, quadrant_images, corrected_params):
        """Re-composite images using corrected alignment parameters with mean blending."""
        
        # Get origin offset
        ox, oy = 0.0, 0.0
        if corrected_params.origin_offset:
            ox, oy = corrected_params.origin_offset
        
        # Build params dict from corrected_params
        params_dict = {}
        for qa in corrected_params.quadrants:
            params_dict[qa.quadrant.value] = {
                'dx': qa.position_shift[0],
                'dy': qa.position_shift[1],
                'rot': qa.rotation_degrees,
                'zoom': getattr(qa, 'zoom_percent', 0.0),
                'w': qa.dimensions[0],
                'h': qa.dimensions[1]
            }
        
        # ALWAYS compute canvas bounds from quadrant positions to ensure no pixels are clipped
        canvas_w, canvas_h, ox, oy = self._compute_canvas_bounds_with_rotation(params_dict, ox, oy)
        logger.info(f"_recomposite: computed bounds: {canvas_w}x{canvas_h}, offset: ({ox:.1f}, {oy:.1f})")
        
        # Create accumulators for mean blending
        sum_canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.float64)
        count_canvas = np.zeros((canvas_h, canvas_w), dtype=np.int32)
        
        # Composite each quadrant
        for q_img in quadrant_images:
            if q_img.quadrant.value not in params_dict:
                continue
            
            p = params_dict[q_img.quadrant.value]
            img = q_img.image_data.copy()
            
            # Convert to uint8 if needed
            if img.dtype == np.uint16:
                img_min, img_max = img.min(), img.max()
                if img_max > img_min:
                    img = ((img - img_min) / (img_max - img_min) * 255).astype(np.uint8)
                else:
                    img = np.zeros_like(img, dtype=np.uint8)
            
            # Convert to RGBA
            if img.ndim == 2:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, 0] = img
                rgba[:, :, 1] = img
                rgba[:, :, 2] = img
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 1:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, 0] = img[:, :, 0]
                rgba[:, :, 1] = img[:, :, 0]
                rgba[:, :, 2] = img[:, :, 0]
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 3:
                rgba = np.zeros((img.shape[0], img.shape[1], 4), dtype=np.uint8)
                rgba[:, :, :3] = img
                rgba[:, :, 3] = 255
                img = rgba
            elif img.ndim == 3 and img.shape[2] == 4:
                img[:, :, 3] = 255
            
            h, w = img.shape[:2]
            rot = p['rot']
            zoom_percent = p.get('zoom', 0.0)
            
            # Calculate scale factor from zoom percent
            scale = 1.0 + (zoom_percent / 100.0)
            
            # Apply zoom and rotation together
            if abs(rot) > 0.01 or abs(zoom_percent) > 0.01:
                center = (w / 2.0, h / 2.0)
                # Get rotation matrix with scale
                rot_matrix = cv2.getRotationMatrix2D(center, -rot, scale)
                
                # Calculate new dimensions after scaling
                new_w = int(w * scale)
                new_h = int(h * scale)
                
                # Adjust matrix for new center
                rot_matrix[0, 2] += (new_w - w) / 2
                rot_matrix[1, 2] += (new_h - h) / 2
                
                img = cv2.warpAffine(img, rot_matrix, (new_w, new_h), 
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
                h, w = img.shape[:2]  # Update dimensions
            
            # Calculate position
            x = int(p['dx'] + ox)
            y = int(p['dy'] + oy)
            
            # Clip bounds
            src_x0 = max(0, -x)
            src_y0 = max(0, -y)
            src_x1 = w - max(0, x + w - canvas_w)
            src_y1 = h - max(0, y + h - canvas_h)
            
            dst_x0 = max(0, x)
            dst_y0 = max(0, y)
            dst_x1 = min(canvas_w, x + w)
            dst_y1 = min(canvas_h, y + h)
            
            if dst_x1 > dst_x0 and dst_y1 > dst_y0 and src_x1 > src_x0 and src_y1 > src_y0:
                src_region = img[src_y0:src_y1, src_x0:src_x1]
                
                # Create mask for pixels with content (alpha > 0)
                content_mask = src_region[:, :, 3] > 0
                
                # Accumulate RGB values and count for mean blending
                for c in range(3):
                    sum_canvas[dst_y0:dst_y1, dst_x0:dst_x1, c] += np.where(
                        content_mask, src_region[:, :, c].astype(np.float64), 0
                    )
                count_canvas[dst_y0:dst_y1, dst_x0:dst_x1] += content_mask.astype(np.int32)
        
        # Compute mean from accumulated values
        valid_mask = count_canvas > 0
        canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)
        
        for c in range(3):
            canvas[:, :, c] = np.where(
                valid_mask,
                (sum_canvas[:, :, c] / np.maximum(count_canvas, 1)).astype(np.uint8),
                0
            )
        
        # Set alpha: fully opaque where we have content (cell layer should be opaque)
        canvas[:, :, 3] = np.where(valid_mask, 255, 0)
        
        # Apply "All" adjustments to the entire composited image (same as preview)
        all_adj = self._quadrant_adjustments.get('All', {'dx': 0, 'dy': 0, 'rot': 0.0})
        total_dx = all_adj['dx']
        total_dy = all_adj['dy']
        total_rot = all_adj['rot']
        
        image_data = canvas
        
        # Apply global rotation if non-zero
        if abs(total_rot) > 0.01:
            h, w = image_data.shape[:2]
            center = (w / 2.0, h / 2.0)
            rot_matrix = cv2.getRotationMatrix2D(center, -total_rot, 1.0)
            
            cos_val = abs(rot_matrix[0, 0])
            sin_val = abs(rot_matrix[0, 1])
            new_w = int(h * sin_val + w * cos_val)
            new_h = int(h * cos_val + w * sin_val)
            
            rot_matrix[0, 2] += (new_w - w) / 2
            rot_matrix[1, 2] += (new_h - h) / 2
            
            image_data = cv2.warpAffine(
                image_data, rot_matrix, (new_w, new_h),
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
            )
            logger.info(f"Applied global rotation: {total_rot}°")
        
        # Apply global translation if non-zero
        if total_dx != 0 or total_dy != 0:
            h, w = image_data.shape[:2]
            trans_matrix = np.float32([[1, 0, total_dx], [0, 1, total_dy]])
            
            image_data = cv2.warpAffine(
                image_data, trans_matrix, (w, h),
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0)
            )
            logger.info(f"Applied global translation: dx={total_dx}, dy={total_dy}")
        
        # Update the result
        self.result.stitched_image_data = image_data
        self._adjusted_image_data = image_data
        
        # Update display
        pixmap = self._numpy_to_qpixmap(image_data)
        self.scene.clear()
        self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.graphics_view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        
        logger.info(f"Regenerated original images: {image_data.shape[1]}x{image_data.shape[0]}px")

