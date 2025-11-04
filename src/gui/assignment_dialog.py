"""
AssignmentDialog - Manual Quadrant Position Assignment
Dialog for users to manually assign quadrant position to ambiguous images
"""

import logging
from typing import Optional
from pathlib import Path

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton,
    QPushButton, QButtonGroup, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

from src.models import Quadrant

logger = logging.getLogger(__name__)


class AssignmentDialog(QDialog):
    """
    Dialog for manual quadrant position assignment.
    
    Shown when:
    - Filename contains ambiguous spatial keywords
    - Filename contains multiple conflicting keywords
    - Filename contains no spatial keywords
    
    Allows user to:
    - View thumbnail preview of the image
    - Select quadrant position via radio buttons
    - Confirm assignment or cancel
    """
    
    def __init__(
        self,
        filename: str,
        image_preview: Optional[np.ndarray] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize assignment dialog.
        
        Args:
            filename: Name of file requiring position assignment
            image_preview: Optional thumbnail preview as NumPy array
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.filename = filename
        self.image_preview = image_preview
        self.selected_quadrant: Optional[Quadrant] = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up dialog layout and components."""
        self.setWindowTitle("Assign Quadrant Position")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Instruction text
        instruction = QLabel(
            "<b>Unable to detect spatial position from filename</b><br>"
            "Please manually assign the quadrant position for this image."
        )
        instruction.setWordWrap(True)
        instruction.setStyleSheet("font-size: 11px; padding: 8px;")
        layout.addWidget(instruction)
        
        # Filename label
        filename_label = QLabel(f"<b>File:</b> {Path(self.filename).name}")
        filename_label.setWordWrap(True)
        filename_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 8px;
                font-size: 11px;
                color: #333333;
            }
        """)
        layout.addWidget(filename_label)
        
        # Image preview (if available)
        if self.image_preview is not None:
            preview_label = QLabel()
            preview_pixmap = self._create_preview_pixmap(self.image_preview, max_size=200)
            preview_label.setPixmap(preview_pixmap)
            preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_label.setStyleSheet("""
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 4px;
                background-color: #ffffff;
            """)
            layout.addWidget(preview_label)
        
        # Quadrant selection group
        selection_group = QWidget()
        selection_layout = QVBoxLayout(selection_group)
        selection_layout.setSpacing(8)
        
        selection_label = QLabel("<b>Select Quadrant Position:</b><br><i>Choose the spatial location of this image in the 2×2 grid</i>")
        selection_label.setStyleSheet("font-size: 11px; color: #555555;")
        selection_layout.addWidget(selection_label)
        
        # Radio buttons for each quadrant
        self.button_group = QButtonGroup(self)
        
        # Create 2x2 grid layout for intuitive position selection
        grid_widget = QWidget()
        grid_layout = QVBoxLayout(grid_widget)
        grid_layout.setSpacing(4)
        
        # North row (NW, NE)
        north_row = QHBoxLayout()
        north_row.setSpacing(20)
        
        self.radio_nw = QRadioButton("NW (North-West / Top-Left)")
        self.radio_nw.setStyleSheet("font-size: 11px; padding: 8px;")
        self.button_group.addButton(self.radio_nw, 0)  # Use integer ID
        north_row.addWidget(self.radio_nw)
        
        north_row.addStretch()
        
        self.radio_ne = QRadioButton("NE (North-East / Top-Right)")
        self.radio_ne.setStyleSheet("font-size: 11px; padding: 8px;")
        self.button_group.addButton(self.radio_ne, 1)  # Use integer ID
        north_row.addWidget(self.radio_ne)
        
        grid_layout.addLayout(north_row)
        
        # Separator
        separator = QLabel()
        separator.setFixedHeight(20)
        grid_layout.addWidget(separator)
        
        # South row (SW, SE)
        south_row = QHBoxLayout()
        south_row.setSpacing(20)
        
        self.radio_sw = QRadioButton("SW (South-West / Bottom-Left)")
        self.radio_sw.setStyleSheet("font-size: 11px; padding: 8px;")
        self.button_group.addButton(self.radio_sw, 2)  # Use integer ID
        south_row.addWidget(self.radio_sw)
        
        south_row.addStretch()
        
        self.radio_se = QRadioButton("SE (South-East / Bottom-Right)")
        self.radio_se.setStyleSheet("font-size: 11px; padding: 8px;")
        self.button_group.addButton(self.radio_se, 3)  # Use integer ID
        south_row.addWidget(self.radio_se)
        
        grid_layout.addLayout(south_row)
        
        grid_widget.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 2px solid #4caf50;
                border-radius: 6px;
                padding: 16px;
            }
            QRadioButton {
                color: #333333;
                font-weight: 500;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        
        selection_layout.addWidget(grid_widget)
        layout.addWidget(selection_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet("padding: 6px 16px; font-size: 10px;")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        self.assign_button = QPushButton("Assign")
        self.assign_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                padding: 6px 20px;
                font-size: 10px;
                font-weight: bold;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.assign_button.setEnabled(False)  # Initially disabled
        self.assign_button.clicked.connect(self._on_assign)
        button_layout.addWidget(self.assign_button)
        
        layout.addLayout(button_layout)
        
        # Connect button group to enable Assign button
        self.button_group.buttonClicked.connect(self._on_selection_changed)
    
    def _create_preview_pixmap(self, image_data: np.ndarray, max_size: int = 200) -> QPixmap:
        """
        Create thumbnail preview QPixmap from NumPy array.
        
        Args:
            image_data: Image as NumPy array
            max_size: Maximum dimension for preview
            
        Returns:
            QPixmap for display
        """
        # Normalize to uint8 if needed
        if image_data.dtype != np.uint8:
            img_min = image_data.min()
            img_max = image_data.max()
            if img_max > img_min:
                image_data = ((image_data - img_min) / (img_max - img_min) * 255).astype(np.uint8)
            else:
                image_data = np.zeros_like(image_data, dtype=np.uint8)
        
        # Downsample if needed
        height, width = image_data.shape[:2]
        if max(height, width) > max_size:
            scale = max_size / max(height, width)
            new_height = int(height * scale)
            new_width = int(width * scale)
            
            # Simple downsampling (could use cv2.resize for better quality)
            if image_data.ndim == 2:
                # Grayscale - simple slicing
                step_h = height // new_height
                step_w = width // new_width
                image_data = image_data[::step_h, ::step_w]
            else:
                # Color - simple slicing
                step_h = height // new_height
                step_w = width // new_width
                image_data = image_data[::step_h, ::step_w, :]
        
        # Convert to QPixmap
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
            # Default to grayscale from first channel
            image_data = image_data[:, :, 0] if image_data.ndim == 3 else image_data
            bytes_per_line = width
            qimage = QImage(
                image_data.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_Grayscale8
            )
        
        # Copy image (important)
        qimage = qimage.copy()
        
        return QPixmap.fromImage(qimage)
    
    def _on_selection_changed(self):
        """Enable Assign button when a selection is made."""
        self.assign_button.setEnabled(True)
    
    def _on_assign(self):
        """Handle Assign button click."""
        # Get selected button ID
        button_id = self.button_group.checkedId()
        if button_id == -1:
            return
        
        # Map integer ID to Quadrant
        id_to_quadrant = {
            0: Quadrant.NW,
            1: Quadrant.NE,
            2: Quadrant.SW,
            3: Quadrant.SE,
        }
        
        self.selected_quadrant = id_to_quadrant.get(button_id)
        
        logger.info(f"User assigned {self.selected_quadrant.value} to {self.filename}")
        
        self.accept()
    
    def get_selected_quadrant(self) -> Optional[Quadrant]:
        """
        Get the quadrant selected by the user.
        
        Returns:
            Selected Quadrant or None if dialog was cancelled
        """
        return self.selected_quadrant

