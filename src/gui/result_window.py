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
    QGraphicsView, QGraphicsScene, QFileDialog, QGroupBox, QFormLayout
)
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
        
        self.result = result
        
        self._setup_ui()
        self._display_result()
    
    def _setup_ui(self):
        """Set up window layout and components."""
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
        
        config_group.setLayout(config_layout)
        info_layout.addWidget(config_group)
        
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
            bytes_per_line = width
            qimage = QImage(
                image_data.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_Grayscale8
            )
        elif image_data.ndim == 3 and image_data.shape[2] == 3:
            image_data = np.ascontiguousarray(image_data)
            bytes_per_line = 3 * width
            qimage = QImage(
                image_data.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888
            )
        else:
            # Fallback to first channel
            image_data = image_data[:, :, 0] if image_data.ndim == 3 else image_data
            bytes_per_line = width
            qimage = QImage(
                image_data.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_Grayscale8
            )
        
        qimage = qimage.copy()
        return QPixmap.fromImage(qimage)
    
    def _on_save_clicked(self):
        """Handle Save As button click."""
        # Show file dialog
        default_name = f"stitched_{self.result.timestamp.strftime('%Y%m%d_%H%M%S')}.{self.result.stitching_config.output_format}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Stitched Image",
            default_name,
            "TIFF Image (*.tif *.tiff);;PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;All Files (*)"
        )
        
        if file_path:
            try:
                # Save full resolution image
                io.save_image(
                    self.result.stitched_image_data,
                    Path(file_path),
                    format=self.result.stitching_config.output_format,
                    compression_level=self.result.stitching_config.compression_level
                )
                
                logger.info(f"Saved stitched image to {file_path}")
                self.save_button.setText("✅ Saved!")
                self.save_button.setEnabled(False)
            
            except Exception as e:
                logger.exception(f"Failed to save image: {e}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self,
                    "Save Failed",
                    f"Could not save image:\n{str(e)}",
                    QMessageBox.StandardButton.Ok
                )

