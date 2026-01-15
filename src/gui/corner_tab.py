from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPixmap, QImage, QPen, QBrush, QColor, QPolygonF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QGraphicsView, QGraphicsScene, QFileDialog, QLabel, QGraphicsEllipseItem, QGraphicsSimpleTextItem, QGraphicsPolygonItem
)
import numpy as np

from src.lib import io
from src.models.corner_annotations import CornerPoint


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._zoom_steps = 0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return super().wheelEvent(event)
        factor = 1.25 if delta > 0 else 0.8
        self.scale(factor, factor)
        if delta > 0:
            self._zoom_steps += 1
        else:
            self._zoom_steps = max(0, self._zoom_steps - 1)
        event.accept()

    def fitInViewRect(self, rect):
        if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        self.resetTransform()
        view_size = self.viewport().size()
        if view_size.width() <= 0 or view_size.height() <= 0:
            return
        sx = view_size.width() / rect.width()
        sy = view_size.height() / rect.height()
        scale_factor = min(sx, sy)
        self.scale(scale_factor, scale_factor)
        self.centerOn(rect.center())
        self._zoom_steps = 0

    def resizeEvent(self, event):
        # If the user hasn't zoomed, keep fitting on resize
        if self._zoom_steps == 0:
            rect = self.sceneRect()
            super().resizeEvent(event)
            self.fitInViewRect(rect)
        else:
            super().resizeEvent(event)


class CornerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: Optional[np.ndarray] = None
        self._points: List[CornerPoint] = []
        self._marker_items: List[QGraphicsEllipseItem] = []
        self._label_items: List[QGraphicsSimpleTextItem] = []
        self._overlay_items: List[QGraphicsPolygonItem] = []
        self._pixmap_item = None

        self.scene = QGraphicsScene(self)
        self.view = ZoomableGraphicsView(self.scene, self)
        self.view.setRenderHints(self.view.renderHints())
        self.view.viewport().installEventFilter(self)

        self.open_btn = QPushButton("Open Image…", self)
        self.save_btn = QPushButton("Save", self)
        self.load_btn = QPushButton("Load", self)
        self.undo_btn = QPushButton("Undo", self)
        self.clear_btn = QPushButton("Clear", self)
        self.fit_btn = QPushButton("Fit Square", self)
        self.toggle_overlay_btn = QPushButton("Toggle Overlay", self)
        self.auto_fit_btn = QPushButton("Auto-fit Square", self)
        self.status_lbl = QLabel("", self)
        self.metrics_lbl = QLabel("", self)

        top = QHBoxLayout()
        top.addWidget(self.open_btn)
        top.addWidget(self.undo_btn)
        top.addWidget(self.clear_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.load_btn)
        top.addWidget(self.fit_btn)
        top.addWidget(self.auto_fit_btn)
        top.addWidget(self.toggle_overlay_btn)
        top.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.status_lbl)
        layout.addWidget(self.metrics_lbl)
        self.setLayout(layout)

        self.open_btn.clicked.connect(self._on_open)
        self.undo_btn.clicked.connect(self._on_undo)
        self.clear_btn.clicked.connect(self._on_clear)
        self.fit_btn.clicked.connect(self._on_fit_clicked)
        self.toggle_overlay_btn.clicked.connect(self._on_toggle_overlay)
        self.save_btn.clicked.connect(self._on_save)
        self.load_btn.clicked.connect(self._on_load)
        self.auto_fit_btn.clicked.connect(self._on_auto_fit)
        self._rms_thresh = 2.0
        self._conf_thresh = 0.7
        self._downscale = 0.5

        self._auto_load_latest()
        self._update_buttons()
        self._overlay_visible = True
        self._loaded_image_path: Optional[Path] = None
        self._last_fit_result = None

    def _auto_load_latest(self):
        latest = io.find_latest_chip_stitched_image()
        if latest:
            self._load_image(latest)

    def _on_open(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Stitched Image",
            "", "Image Files (*.tif *.tiff *.png *.jpg *.jpeg);;All Files (*)"
        )
        if file_path:
            self._load_image(Path(file_path))

    def _load_image(self, path: Path):
        try:
            img, _ = io.load_image(path)
            # Convert to displayable format (grayscale, RGB, or RGBA)
            if img.ndim == 2:
                img = np.ascontiguousarray(img)
                qimg = QImage(bytes(img.data), img.shape[1], img.shape[0], img.strides[0], QImage.Format.Format_Grayscale8)
            elif img.ndim == 3 and img.shape[2] == 4:
                # RGBA
                img = np.ascontiguousarray(img)
                qimg = QImage(bytes(img.data), img.shape[1], img.shape[0], img.strides[0], QImage.Format.Format_RGBA8888)
            else:
                # Ensure 3 channels for RGB
                if img.ndim == 3 and img.shape[2] >= 3:
                    data = np.ascontiguousarray(img[:, :, :3])
                else:
                    data = np.ascontiguousarray(np.repeat(img[:, :, :1], 3, axis=2))
                qimg = QImage(bytes(data.data), data.shape[1], data.shape[0], data.strides[0], QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg.copy())
            self.scene.clear()
            self._pixmap_item = self.scene.addPixmap(pix)
            # Fit exactly to the pixmap bounds to use full available space
            self.view.setSceneRect(self._pixmap_item.boundingRect())
            self.view.fitInViewRect(self._pixmap_item.boundingRect())
            self._image = img
            self._points = []
            self._loaded_image_path = path
            self._clear_markers()
            self._clear_overlay()
            self.status_lbl.setText(f"Loaded: {path.name}")
            self._update_buttons()
        except Exception as e:
            self.status_lbl.setText(f"Failed to load: {e}")

    def _on_undo(self):
        if self._points:
            self._points.pop()
            # Remove last marker/label
            if self._marker_items:
                item = self._marker_items.pop()
                self.scene.removeItem(item)
            if self._label_items:
                item = self._label_items.pop()
                self.scene.removeItem(item)
            # Re-number labels
            for i, lbl in enumerate(self._label_items, start=1):
                lbl.setText(str(i))
            self.status_lbl.setText(self._points_status())
            self._clear_overlay()
        self._update_buttons()

    def _on_clear(self):
        self._points = []
        self._clear_markers()
        self._clear_overlay()
        self.status_lbl.setText("Cleared points")
        self._update_buttons()

    def _update_buttons(self):
        self.fit_btn.setEnabled(len(self._points) == 4)
        # Minimal completeness indicator (≥2) is conveyed via status for now
        if len(self._points) >= 2:
            self.status_lbl.setText(self._points_status() + " (min complete)")
        else:
            self.status_lbl.setText(self._points_status())
        self.toggle_overlay_btn.setEnabled(len(self._overlay_items) > 0)

    def _points_status(self) -> str:
        return f"Points: {len(self._points)}"

    def _clear_markers(self):
        for item in self._marker_items:
            self.scene.removeItem(item)
        for item in self._label_items:
            self.scene.removeItem(item)
        self._marker_items.clear()
        self._label_items.clear()

    def _clear_overlay(self):
        for item in self._overlay_items:
            self.scene.removeItem(item)
        self._overlay_items.clear()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QMouseEvent
        if obj is self.view.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            me: QMouseEvent = event
            if me.button() == Qt.MouseButton.LeftButton:
                self._handle_click(me.position())
                return True
        return super().eventFilter(obj, event)

    def _handle_click(self, pos: QPointF):
        if self._image is None or self._pixmap_item is None:
            return
        scene_pt = self.view.mapToScene(int(pos.x()), int(pos.y()))
        x = int(round(scene_pt.x()))
        y = int(round(scene_pt.y()))
        h, w = self._image.shape[0], self._image.shape[1]
        if x < 0 or y < 0 or x >= w or y >= h:
            # out-of-bounds: ignore and show non-intrusive note
            self.status_lbl.setText("Click ignored (outside image bounds)")
            return
        if len(self._points) >= 4:
            self.status_lbl.setText("Already have 4 points. Use Undo or Clear.")
            return
        cp = CornerPoint(index=len(self._points) + 1, x=x, y=y)
        self._points.append(cp)
        self._add_marker(cp)
        self.status_lbl.setText(self._points_status())
        self._update_buttons()

    def _add_marker(self, cp: CornerPoint):
        r = 4.0
        pen = QPen(QColor("#FFD166"))
        brush = QBrush(QColor("#FFD166"))
        ellipse = QGraphicsEllipseItem(cp.x - r, cp.y - r, 2 * r, 2 * r)
        ellipse.setPen(pen)
        ellipse.setBrush(brush)
        self.scene.addItem(ellipse)
        label = QGraphicsSimpleTextItem(str(cp.index))
        label.setBrush(QBrush(QColor("#FFFFFF")))
        label.setPos(cp.x + 6, cp.y - 6)
        self.scene.addItem(label)
        self._marker_items.append(ellipse)
        self._label_items.append(label)

    def _on_fit_clicked(self):
        if len(self._points) != 4:
            self.status_lbl.setText("Fit requires exactly 4 points")
            return
        from src.lib.corner_fit import fit_square
        pts = [(p.x, p.y) for p in self._points]
        try:
            result = fit_square(pts)
            # Store the fit result for saving
            self._last_fit_result = result
            self._clear_overlay()
            # Draw polygon from result corners
            poly = QPolygonF()
            for cp in result.corners:
                poly.append(QPointF(float(cp.x), float(cp.y)))
            polygon_item = QGraphicsPolygonItem(poly)
            poly_pen = QPen(QColor("#44FF88"))
            poly_pen.setWidth(2)
            polygon_item.setPen(poly_pen)
            self.scene.addItem(polygon_item)
            self._overlay_items.append(polygon_item)
            self._overlay_visible = True
            self._update_overlay_visibility()
            self._update_metrics(result)
        except Exception as e:
            self.status_lbl.setText(f"Fit error: {e}")

    def _update_metrics(self, result):
        self.metrics_lbl.setText(
            f"Fit metrics — side: {result.side_length:.1f}px | rotation: {result.rotation_degrees:.1f}° | "
            f"RMS: {result.rms_residual_px:.2f}px | residuals: {', '.join(f'{r:.2f}' for r in result.residuals_px)}"
        )

    def _on_toggle_overlay(self):
        if not self._overlay_items:
            return
        self._overlay_visible = not self._overlay_visible
        self._update_overlay_visibility()

    def _update_overlay_visibility(self):
        for item in self._overlay_items:
            item.setVisible(self._overlay_visible)
        self.toggle_overlay_btn.setText("Hide Overlay" if self._overlay_visible else "Show Overlay")
        self.toggle_overlay_btn.setEnabled(len(self._overlay_items) > 0)

    def _derive_json_default_name(self) -> str:
        if not self._loaded_image_path:
            return "annotations.json"
        stem = self._loaded_image_path.stem
        quad = stem[-2:].upper() if len(stem) >= 2 else ""
        if quad in {"NE", "NW", "SE", "SW"}:
            prefix = stem[:-2]
        else:
            prefix = stem
        return f"{prefix}.json"

    def _on_save(self):
        from src.models.corner_annotations import CornerAnnotationFile
        if not self._loaded_image_path:
            self.status_lbl.setText("Open an image before saving annotations")
            return
        default_name = self._derive_json_default_name()
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Save Annotations", str(self._loaded_image_path.parent / default_name), "JSON (*.json)"
        )
        if not out_path:
            return
        caf = CornerAnnotationFile(
            version="1.0",
            image_path=str(self._loaded_image_path),
            points=self._points.copy(),
            fit=self._last_fit_result,
            created_at=datetime.now(),
            provenance={
                "source_czi_prefix": default_name[:-5],
                "stitched_image_path": str(self._loaded_image_path),
                "thresholds": {"rms_px": 2.0, "confidence_min": 0.7},
                "resolution_strategy": {"mode": "multiscale", "downscale": 0.5},
            },
        )
        try:
            io.save_corner_annotations(Path(out_path), caf)
            self.status_lbl.setText(f"Saved: {Path(out_path).name}")
        except Exception as e:
            self.status_lbl.setText(f"Save failed: {e}")

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Annotations", "", "JSON (*.json)")
        if not path:
            return
        try:
            caf = io.load_corner_annotations(Path(path))
            # reset state
            self._points = []
            self._clear_markers()
            self._clear_overlay()
            # apply points
            for p in caf.points[:4]:
                self._points.append(CornerPoint(index=len(self._points) + 1, x=p.x, y=p.y))
                self._add_marker(self._points[-1])
            # apply fit if present
            if caf.fit:
                self._last_fit_result = caf.fit
                poly = QPolygonF()
                for cp in caf.fit.corners:
                    poly.append(QPointF(float(cp.x), float(cp.y)))
                polygon_item = QGraphicsPolygonItem(poly)
                poly_pen = QPen(QColor("#44FF88"))
                poly_pen.setWidth(2)
                polygon_item.setPen(poly_pen)
                self.scene.addItem(polygon_item)
                self._overlay_items.append(polygon_item)
                self._overlay_visible = True
                self._update_overlay_visibility()
                self._update_metrics(caf.fit)
            self.status_lbl.setText(f"Loaded annotations: {Path(path).name}")
            self._update_buttons()
        except Exception as e:
            self.status_lbl.setText(f"Load failed: {e}")

    def _on_auto_fit(self):
        if self._image is None:
            self.status_lbl.setText("Open an image before auto-fit")
            return
        from src.lib.corner_autofit import auto_fit_square
        try:
            proposal, conf = auto_fit_square(self._image, downscale=self._downscale)
            passes = (proposal.rms_residual_px <= self._rms_thresh) and (conf >= self._conf_thresh)
            label = "confident" if passes else "low confidence"
            # Show preview and ask Accept/Discard
            self._clear_overlay()
            poly = QPolygonF()
            for cp in proposal.corners:
                poly.append(QPointF(float(cp.x), float(cp.y)))
            item = QGraphicsPolygonItem(poly)
            pen = QPen(QColor("#44FF88"))
            pen.setWidth(2)
            item.setPen(pen)
            self.scene.addItem(item)
            self._overlay_items.append(item)
            self._overlay_visible = True
            self._update_overlay_visibility()
            self._update_metrics(proposal)
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "Auto-fit Result",
                f"Auto-fit is {label}.\n"
                f"RMS={proposal.rms_residual_px:.2f}px (≤ {self._rms_thresh})\n"
                f"Confidence={conf:.2f} (≥ {self._conf_thresh})\n\n"
                "Accept this proposal?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes if passes else QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._last_fit_result = proposal
                self.status_lbl.setText("Auto-fit accepted")
            else:
                self._clear_overlay()
                self.status_lbl.setText("Auto-fit discarded")
        except Exception as e:
            self.status_lbl.setText(f"Auto-fit failed: {e}")


