"""
QuadrantViewer Widget - Single Quadrant Image Display
Displays one microscopy image with zoom/pan controls and info footer
"""

import logging
from typing import Optional

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGraphicsView, QGraphicsScene
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPixmap, QImage, QPainter

from src.models.quadrant_image import QuadrantImage

logger = logging.getLogger(__name__)


class QuadrantViewer(QWidget):
    """
    Widget for displaying a single quadrant image with zoom/pan controls.
    
    Features:
    - Image display with automatic fitting
    - Mouse wheel zoom (10%-400% range)
    - Click-and-drag panning
    - Position label header
    - Dimensions and file size footer
    - Synchronized zoom/pan support
    
    Signals:
        zoom_changed(float): Emitted when zoom level changes (scale factor)
        pan_changed(int, int): Emitted when pan position changes (dx, dy)
    """
    
    zoom_changed = pyqtSignal(float)
    pan_changed = pyqtSignal(int, int)
    
    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize QuadrantViewer widget."""
        super().__init__(parent)
        
        self._quadrant_image: Optional[QuadrantImage] = None
        self._zoom_level: float = 1.0  # Current zoom scale factor
        self._pan_offset: QPoint = QPoint(0, 0)  # Current pan offset
        self._is_panning: bool = False  # Mouse drag state
        self._last_pan_point: Optional[QPoint] = None  # Last mouse position during drag
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up widget layout and components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        
        # Position label header
        self.position_label = QLabel("Empty")
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 4px;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.position_label)
        
        # Graphics view for image display
        self.graphics_view = QGraphicsView()
        self.graphics_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.graphics_view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.graphics_view.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #cccccc;
                border-radius: 3px;
                background-color: #ffffff;
            }
        """)
        
        # Create scene
        self.scene = QGraphicsScene()
        self.graphics_view.setScene(self.scene)
        
        # Install event filter for mouse events
        self.graphics_view.viewport().installEventFilter(self)
        
        layout.addWidget(self.graphics_view)
        
        # Info footer
        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 2px;
                font-size: 9px;
                color: #666666;
            }
        """)
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
    
    def set_image(self, quadrant_image: QuadrantImage) -> None:
        """
        Display a quadrant image in this viewer.
        
        Converts NumPy array to QPixmap and displays in QGraphicsView.
        Updates position label and info footer.
        
        Args:
            quadrant_image: QuadrantImage with loaded image_data
        """
        self._quadrant_image = quadrant_image
        
        # Update position label
        if quadrant_image.quadrant:
            self.position_label.setText(quadrant_image.position_label)
            self.position_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e9;
                    border: 2px solid #4caf50;
                    border-radius: 3px;
                    padding: 4px;
                    font-weight: bold;
                    font-size: 11px;
                    color: #2e7d32;
                }
            """)
        else:
            self.position_label.setText("Unassigned")
        
        # Update info footer
        size_mb = quadrant_image.memory_size_mb()
        self.info_label.setText(
            f"{quadrant_image.width}×{quadrant_image.height}px | "
            f"{size_mb:.1f} MB | "
            f"{quadrant_image.filename}"
        )
        
        # Convert NumPy array to QPixmap
        if quadrant_image.image_data is not None:
            pixmap = self._numpy_to_qpixmap(quadrant_image.image_data)
            
            # Clear scene and add pixmap
            self.scene.clear()
            self.scene.addPixmap(pixmap)
            
            # Fit to view initially
            self.graphics_view.fitInView(
                self.scene.sceneRect(),
                Qt.AspectRatioMode.KeepAspectRatio
            )
            
            logger.info(f"Displayed image in {quadrant_image.position_label} viewer")
        
        # Add green border indicator
        self.graphics_view.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #4caf50;
                border-radius: 3px;
                background-color: #ffffff;
            }
        """)
    
    def _numpy_to_qpixmap(self, image_data: np.ndarray) -> QPixmap:
        """
        Convert NumPy array to QPixmap.
        
        Args:
            image_data: NumPy array with shape (H, W) or (H, W, C)
            
        Returns:
            QPixmap ready for display
        """
        # Normalize to uint8 if needed
        if image_data.dtype != np.uint8:
            # Auto-scale to 0-255 range
            img_min = image_data.min()
            img_max = image_data.max()
            if img_max > img_min:
                image_data = ((image_data - img_min) / (img_max - img_min) * 255).astype(np.uint8)
            else:
                image_data = np.zeros_like(image_data, dtype=np.uint8)
        
        height, width = image_data.shape[:2]
        
        # Determine image format
        if image_data.ndim == 2:
            # Grayscale
            bytes_per_line = width
            qimage = QImage(
                image_data.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_Grayscale8
            )
        elif image_data.ndim == 3:
            if image_data.shape[2] == 3:
                # RGB
                # Convert to contiguous array for Qt
                image_data = np.ascontiguousarray(image_data)
                bytes_per_line = 3 * width
                qimage = QImage(
                    image_data.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888
                )
            elif image_data.shape[2] == 4:
                # RGBA
                image_data = np.ascontiguousarray(image_data)
                bytes_per_line = 4 * width
                qimage = QImage(
                    image_data.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGBA8888
                )
            else:
                # Take first channel
                image_data = image_data[:, :, 0]
                bytes_per_line = width
                qimage = QImage(
                    image_data.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_Grayscale8
                )
        else:
            raise ValueError(f"Unsupported image shape: {image_data.shape}")
        
        # Copy the image data (important: QImage doesn't own the numpy data)
        qimage = qimage.copy()
        
        return QPixmap.fromImage(qimage)
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming."""
        if self._quadrant_image is None or self._quadrant_image.image_data is None:
            return
        
        # Get zoom delta
        delta = event.angleDelta().y()
        
        # Calculate new zoom level (10% steps)
        zoom_factor = 1.1 if delta > 0 else 0.9
        new_zoom = self._zoom_level * zoom_factor
        
        # Clamp to 10%-400% range
        new_zoom = max(0.1, min(4.0, new_zoom))
        
        if new_zoom != self._zoom_level:
            self._zoom_level = new_zoom
            self._apply_zoom()
            self.zoom_changed.emit(self._zoom_level)
    
    def _apply_zoom(self):
        """Apply current zoom level to view."""
        # Reset transform and apply zoom
        self.graphics_view.resetTransform()
        self.graphics_view.scale(self._zoom_level, self._zoom_level)
    
    def eventFilter(self, source, event):
        """Handle mouse events for panning."""
        if source == self.graphics_view.viewport():
            if event.type() == event.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._is_panning = True
                    self._last_pan_point = event.pos()
                    self.graphics_view.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return True
            
            elif event.type() == event.Type.MouseMove:
                if self._is_panning and self._last_pan_point is not None:
                    # Calculate delta
                    delta = event.pos() - self._last_pan_point
                    self._last_pan_point = event.pos()
                    
                    # Update pan offset
                    self._pan_offset += delta
                    
                    # Emit pan signal
                    self.pan_changed.emit(delta.x(), delta.y())
                    
                    # Update scroll bars
                    h_bar = self.graphics_view.horizontalScrollBar()
                    v_bar = self.graphics_view.verticalScrollBar()
                    h_bar.setValue(h_bar.value() - delta.x())
                    v_bar.setValue(v_bar.value() - delta.y())
                    
                    return True
            
            elif event.type() == event.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._is_panning = False
                    self._last_pan_point = None
                    self.graphics_view.setCursor(Qt.CursorShape.ArrowCursor)
                    return True
        
        return super().eventFilter(source, event)
    
    def sync_zoom(self, zoom_level: float) -> None:
        """
        Synchronize zoom level from another viewer.
        
        Args:
            zoom_level: Target zoom level (0.1-4.0)
        """
        if self._zoom_level != zoom_level:
            self._zoom_level = zoom_level
            self._apply_zoom()
    
    def sync_pan(self, dx: int, dy: int) -> None:
        """
        Synchronize pan offset from another viewer.
        
        Args:
            dx: Horizontal pan delta in pixels
            dy: Vertical pan delta in pixels
        """
        # Update scroll bars to match pan delta
        h_bar = self.graphics_view.horizontalScrollBar()
        v_bar = self.graphics_view.verticalScrollBar()
        h_bar.setValue(h_bar.value() - dx)
        v_bar.setValue(v_bar.value() - dy)
    
    def clear(self) -> None:
        """Clear the displayed image and reset to empty state."""
        self._quadrant_image = None
        self.scene.clear()
        self.position_label.setText("Empty")
        self.position_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                border-radius: 3px;
                padding: 4px;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.info_label.setText("")
        self.graphics_view.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #cccccc;
                border-radius: 3px;
                background-color: #ffffff;
            }
        """)
        self._zoom_level = 1.0
        self._pan_offset = QPoint(0, 0)

