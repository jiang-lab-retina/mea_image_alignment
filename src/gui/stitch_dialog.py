"""
StitchDialog - Stitching Parameter Configuration
Dialog for users to configure stitching parameters before processing
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSlider, QPushButton, QFormLayout, QWidget, QGroupBox
)
from PyQt6.QtCore import Qt

from src.models import StitchingConfig

logger = logging.getLogger(__name__)


class StitchDialog(QDialog):
    """
    Dialog for configuring stitching parameters.
    
    Allows users to adjust:
    - Alignment method (ORB, SIFT, AKAZE)
    - Blend mode (linear, multiband, feather)
    - Overlap threshold (5-50%)
    - Output format (TIFF, PNG, JPEG)
    - Compression level (0-9)
    
    All controls include scientific tooltips explaining parameters.
    """
    
    def __init__(self, default_config: Optional[StitchingConfig] = None, parent: Optional[QWidget] = None):
        """
        Initialize stitch dialog.
        
        Args:
            default_config: Starting configuration (defaults to StitchingConfig.default())
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config = default_config or StitchingConfig.default()
        
        self._setup_ui()
        self._load_config()
    
    def _setup_ui(self):
        """Set up dialog layout and components."""
        self.setWindowTitle("Stitching Parameters")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Title
        title = QLabel("<h3>Configure Stitching Parameters</h3>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Algorithm group
        algo_group = QGroupBox("Algorithm Settings")
        algo_layout = QFormLayout()
        algo_layout.setSpacing(10)
        
        # Alignment method
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems(["orb", "sift", "akaze", "skimage"])
        self.alignment_combo.setToolTip(
            "<b>Alignment Method</b><br>"
            "<b>ORB:</b> Fast, good for textured images (default)<br>"
            "<b>SIFT:</b> Robust, handles scale/rotation well (slower)<br>"
            "<b>AKAZE:</b> Balance of speed and quality<br>"
            "<b>Scikit-image:</b> Phase correlation with sub-pixel accuracy (best for cells/uniform textures)"
        )
        algo_layout.addRow("Alignment Method:", self.alignment_combo)
        
        # Blend mode
        self.blend_combo = QComboBox()
        self.blend_combo.addItems(["linear", "multiband", "feather"])
        self.blend_combo.setToolTip(
            "<b>Blend Mode</b><br>"
            "<b>Linear:</b> Simple distance-based blending<br>"
            "<b>Multiband:</b> Multi-resolution blending for seamless transitions (best quality)<br>"
            "<b>Feather:</b> Gradual feathering at edges"
        )
        algo_layout.addRow("Blend Mode:", self.blend_combo)
        
        algo_group.setLayout(algo_layout)
        layout.addWidget(algo_group)
        
        # Quality group
        quality_group = QGroupBox("Quality Settings")
        quality_layout = QFormLayout()
        quality_layout.setSpacing(10)
        
        # Overlap threshold
        overlap_widget = QWidget()
        overlap_layout = QVBoxLayout(overlap_widget)
        overlap_layout.setContentsMargins(0, 0, 0, 0)
        
        self.overlap_slider = QSlider(Qt.Orientation.Horizontal)
        self.overlap_slider.setMinimum(5)
        self.overlap_slider.setMaximum(50)
        self.overlap_slider.setValue(15)
        self.overlap_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.overlap_slider.setTickInterval(5)
        self.overlap_slider.setToolTip(
            "<b>Overlap Threshold</b><br>"
            "Minimum expected overlap between adjacent images.<br>"
            "Lower values (5-10%): Allow stitching with minimal overlap<br>"
            "Higher values (20-50%): Require more overlap for better alignment"
        )
        
        self.overlap_label = QLabel("15%")
        self.overlap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlap_label.setStyleSheet("font-weight: bold;")
        
        self.overlap_slider.valueChanged.connect(
            lambda v: self.overlap_label.setText(f"{v}%")
        )
        
        overlap_layout.addWidget(self.overlap_slider)
        overlap_layout.addWidget(self.overlap_label)
        
        quality_layout.addRow("Overlap Threshold:", overlap_widget)
        
        # Resize strategy
        self.resize_combo = QComboBox()
        self.resize_combo.addItems(["largest", "smallest", "average"])
        self.resize_combo.setToolTip(
            "<b>Resize Strategy</b><br>"
            "<b>Largest:</b> Resize all to largest image (preserves detail)<br>"
            "<b>Smallest:</b> Resize all to smallest image (faster processing)<br>"
            "<b>Average:</b> Resize all to average dimension"
        )
        quality_layout.addRow("Resize Strategy:", self.resize_combo)
        
        # Interpolation
        self.interp_combo = QComboBox()
        self.interp_combo.addItems(["linear", "cubic", "lanczos"])
        self.interp_combo.setToolTip(
            "<b>Interpolation Method</b><br>"
            "<b>Linear:</b> Fast, good for most cases<br>"
            "<b>Cubic:</b> Higher quality, slower<br>"
            "<b>Lanczos:</b> Best quality, slowest"
        )
        quality_layout.addRow("Interpolation:", self.interp_combo)
        
        quality_group.setLayout(quality_layout)
        layout.addWidget(quality_group)
        
        # Alignment Limits group
        limits_group = QGroupBox("Alignment Limits")
        limits_layout = QFormLayout()
        limits_layout.setSpacing(10)
        
        # Max rotation degrees
        rotation_widget = QWidget()
        rotation_layout = QVBoxLayout(rotation_widget)
        rotation_layout.setContentsMargins(0, 0, 0, 0)
        
        self.rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotation_slider.setMinimum(0)
        self.rotation_slider.setMaximum(20)  # 0-20 degrees
        self.rotation_slider.setValue(5)
        self.rotation_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.rotation_slider.setTickInterval(5)
        self.rotation_slider.setToolTip(
            "<b>Maximum Rotation</b><br>"
            "Maximum allowed rotation angle during alignment.<br>"
            "Lower values (1-5°): Stricter, rejects large rotations<br>"
            "Higher values (10-20°): More permissive for rotated samples"
        )
        
        self.rotation_label = QLabel("±5°")
        self.rotation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rotation_label.setStyleSheet("font-weight: bold;")
        
        self.rotation_slider.valueChanged.connect(
            lambda v: self.rotation_label.setText(f"±{v}°")
        )
        
        rotation_layout.addWidget(self.rotation_slider)
        rotation_layout.addWidget(self.rotation_label)
        
        limits_layout.addRow("Max Rotation:", rotation_widget)
        
        # Max zoom percent
        zoom_widget = QWidget()
        zoom_layout = QVBoxLayout(zoom_widget)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(0)
        self.zoom_slider.setMaximum(10)  # 0-10%
        self.zoom_slider.setValue(5)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(2)
        self.zoom_slider.setToolTip(
            "<b>Maximum Zoom/Scale</b><br>"
            "Maximum allowed scale adjustment during alignment.<br>"
            "0%: No scaling allowed (translation only)<br>"
            "5%: Allow ±5% scale (0.95x to 1.05x)<br>"
            "10%: Allow ±10% scale for significant magnification differences"
        )
        
        self.zoom_label = QLabel("±5%")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setStyleSheet("font-weight: bold;")
        
        self.zoom_slider.valueChanged.connect(
            lambda v: self.zoom_label.setText(f"±{v}%")
        )
        
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(self.zoom_label)
        
        limits_layout.addRow("Max Zoom:", zoom_widget)
        
        limits_group.setLayout(limits_layout)
        layout.addWidget(limits_group)
        
        # Output group
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout()
        output_layout.setSpacing(10)
        
        # Output format
        self.format_combo = QComboBox()
        self.format_combo.addItems(["tiff", "png", "jpeg"])
        self.format_combo.setToolTip(
            "<b>Output Format</b><br>"
            "<b>TIFF:</b> Lossless, supports 16-bit, large files (recommended)<br>"
            "<b>PNG:</b> Lossless, 8-bit, smaller files<br>"
            "<b>JPEG:</b> Lossy, 8-bit, smallest files"
        )
        output_layout.addRow("Output Format:", self.format_combo)
        
        # Compression level
        comp_widget = QWidget()
        comp_layout = QVBoxLayout(comp_widget)
        comp_layout.setContentsMargins(0, 0, 0, 0)
        
        self.compression_slider = QSlider(Qt.Orientation.Horizontal)
        self.compression_slider.setMinimum(0)
        self.compression_slider.setMaximum(9)
        self.compression_slider.setValue(5)
        self.compression_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.compression_slider.setTickInterval(1)
        self.compression_slider.setToolTip(
            "<b>Compression Level</b><br>"
            "0 = No compression (fastest, largest files)<br>"
            "5 = Balanced (recommended)<br>"
            "9 = Maximum compression (slowest, smallest files)"
        )
        
        self.compression_label = QLabel("5")
        self.compression_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compression_label.setStyleSheet("font-weight: bold;")
        
        self.compression_slider.valueChanged.connect(
            lambda v: self.compression_label.setText(str(v))
        )
        
        comp_layout.addWidget(self.compression_slider)
        comp_layout.addWidget(self.compression_label)
        
        output_layout.addRow("Compression:", comp_widget)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        stitch_button = QPushButton("Stitch Images")
        stitch_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                padding: 8px 24px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        stitch_button.clicked.connect(self._on_stitch)
        button_layout.addWidget(stitch_button)
        
        layout.addLayout(button_layout)
    
    def _load_config(self):
        """Load current configuration into UI controls."""
        self.alignment_combo.setCurrentText(self.config.alignment_method)
        self.blend_combo.setCurrentText(self.config.blend_mode)
        self.overlap_slider.setValue(int(self.config.overlap_threshold_percent))
        self.resize_combo.setCurrentText(self.config.resize_strategy)
        self.interp_combo.setCurrentText(self.config.interpolation_method)
        self.format_combo.setCurrentText(self.config.output_format)
        self.compression_slider.setValue(self.config.compression_level)
        self.rotation_slider.setValue(int(self.config.max_rotation_degrees))
        self.zoom_slider.setValue(int(self.config.max_zoom_percent))
    
    def _reset_to_defaults(self):
        """Reset all parameters to default values."""
        self.config = StitchingConfig.default()
        self._load_config()
        logger.info("Reset stitching parameters to defaults")
    
    def _on_stitch(self):
        """Validate parameters and accept dialog."""
        # Validate parameters
        overlap = self.overlap_slider.value()
        if not (5 <= overlap <= 50):
            logger.error(f"Invalid overlap threshold: {overlap}")
            return
        
        compression = self.compression_slider.value()
        if not (0 <= compression <= 9):
            logger.error(f"Invalid compression level: {compression}")
            return
        
        rotation = self.rotation_slider.value()
        zoom = self.zoom_slider.value()
        
        # Create new config from UI values
        self.config = StitchingConfig(
            alignment_method=self.alignment_combo.currentText(),
            blend_mode=self.blend_combo.currentText(),
            overlap_threshold_percent=float(overlap),
            resize_strategy=self.resize_combo.currentText(),
            interpolation_method=self.interp_combo.currentText(),
            confidence_threshold=self.config.confidence_threshold,  # Keep existing
            output_format=self.format_combo.currentText(),
            compression_level=compression,
            missing_quadrant_fill=self.config.missing_quadrant_fill,  # Keep existing
            max_rotation_degrees=float(rotation),
            max_zoom_percent=float(zoom)
        )
        
        logger.info(
            f"Stitching configured: alignment={self.config.alignment_method}, "
            f"blend={self.config.blend_mode}, overlap={self.config.overlap_threshold_percent}%, "
            f"max_rotation=±{rotation}°, max_zoom=±{zoom}%"
        )
        
        self.accept()
    
    def get_config(self) -> StitchingConfig:
        """
        Get configured stitching parameters.
        
        Returns:
            StitchingConfig with user-selected parameters
        """
        return self.config

