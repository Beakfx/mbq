#mbq_functions.py
#© Beakfx, 2026
#combines ImageFolder, ImageCanvas, WorkflowCache classes to single file.

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel,
)
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QPainter, QImageReader, QFont
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtOpenGLWidgets import QOpenGLWidget
import os
from pathlib import Path
from datetime import datetime



class ImageFolder:
    SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

    def __init__(self, folder_path, start_file=None):
        """
        folder_path: Path to scan for images
        start_file: optional file path to set as the initial index
        """
        self.folder_path = Path(folder_path)
        self.files = []
        self.subdirs = []
        self.index = 0

        self.scan_folder()

        # If a specific start file was given, set index to that
        if start_file:
            try:
                self.index = [f["path"] for f in self.files].index(str(Path(start_file)))
            except ValueError:
                pass  # if not found, just leave at 0

    def scan_folder(self):
        """Populate self.files with image metadata"""
        if not self.folder_path.exists():
            self.files = []
            self.subdirs = []
            return

        all_files = [
            f for f in self.folder_path.iterdir()
            if f.suffix.lower() in self.SUPPORTED_EXTS and f.is_file()
        ]

        self.files = []
        for f in sorted(all_files, key=lambda x: x.name.lower()):
            # Get basic info
            file_info = {
                "path": str(f),
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime),
            }

            # Sniff image dimensions without loading fully
            try:
                reader = QImageReader(str(f))
                if reader.canRead():
                    size = reader.size()
                    file_info["width"] = size.width()
                    file_info["height"] = size.height()
                else:
                    file_info["width"] = None
                    file_info["height"] = None
            except Exception as e:
                print(f"⚠️ Could not read image size for {f.name}: {e}")
                file_info["width"] = None
                file_info["height"] = None

            self.files.append(file_info)

        self.subdirs = sorted(
            [d for d in self.folder_path.iterdir()
             if d.is_dir() and not d.name.startswith('.')],
            key=lambda d: d.name.lower()
        )
        self.index = 0

    def current(self):
        if self.files:
            return self.files[self.index]
        return None

    def next(self):
        if not self.files:
            return None
        self.index = (self.index + 1) % len(self.files)
        return self.current()

    def prev(self):
        if not self.files:
            return None
        self.index = (self.index - 1) % len(self.files)
        return self.current()

    def remove(self, path: str):
        try:
            idx = [f["path"] for f in self.files].index(path)
        except ValueError:
            return
        self.files.pop(idx)
        if self.files:
            self.index = min(idx, len(self.files) - 1)
        else:
            self.index = 0






"""this defines the 'canvas' class, meaning the area where images are dropped and displayed"""

class ImageCanvas(QGraphicsView):
    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(Qt.black)
        self.setAcceptDrops(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.image_item: QGraphicsPixmapItem | None = None
        self._original_pixmap: QPixmap | None = None   # full-res source, never overwritten
        self._native_size = None                        # original_pixmap.size(), cached
        self._lod_active: bool = False                  # True if image_item holds a resample
        self._lod_timer = QTimer(self)
        self._lod_timer.setSingleShot(True)
        self._lod_timer.timeout.connect(self._apply_lod)
        self._LOD_THRESHOLD = 0.5     # below this effective scale, swap to a resample
        self._LOD_DEBOUNCE_MS = 75    # tune after visual testing
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setViewport(QOpenGLWidget())
        self.setFocusPolicy(Qt.StrongFocus)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)

        self.zoom_locked = False
        self.fit_locked  = False
        self._pan_start = None
        self._middle_press_pos = None
        self._zoom_anchor_vp = None
        self._zoom_anchor_scene = None
        self._overlay_label: QLabel | None = None
        self._wedge_corner: str = "bottom_left"

        self._hint_label = QLabel("Drop an image here  ·  Ctrl+O", self.viewport())
        self._hint_label.setAlignment(Qt.AlignCenter)
        self._hint_label.setStyleSheet(
            "color: #555; font: 16px 'Courier New'; background: transparent;"
        )
        self._hint_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._hint_label.setGeometry(0, 0,
            self.viewport().width(), self.viewport().height())
        self._hint_label.show()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Right, Qt.Key_Left):
            main_window = self.window()
            if main_window:
                main_window.keyPressEvent(event)
            event.accept()
        else:
            super().keyPressEvent(event)

    def _zoom_at(self, factor: float):
        if not (0.02 < self.transform().m11() * factor < 100.0):
            return
        self.scale(factor, factor)
        # Keep the press-point anchor fixed in the viewport
        new_vp = self.mapFromScene(self._zoom_anchor_scene)
        delta = new_vp - self._zoom_anchor_vp
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + delta.x())
        self.verticalScrollBar().setValue(self.verticalScrollBar().value() + delta.y())
        self._schedule_lod_check()

    def _schedule_lod_check(self):
        self._lod_timer.start(self._LOD_DEBOUNCE_MS)

    def _apply_lod(self):
        """Swap to/from a resampled pixmap when zoomed past _LOD_THRESHOLD.

        Qt's bilinear minification (no mipmaps) aliases badly once the display
        scale drops far below 1:1 — worst on high-frequency content like UI
        screenshot text. Below threshold, substitute a software-resampled
        downscale (a real weighted resample) generated fresh from the original
        pixmap every time, never from a previously-downscaled one, so repeated
        zoom in/out never compounds quality loss. The swap uses the item's own
        setScale() rather than the view's transform, so transform().m11() stays
        a reliable "real" zoom level for everything else that reads it.
        """
        if self.image_item is None or self._original_pixmap is None:
            return

        scale = self.transform().m11()

        if scale >= self._LOD_THRESHOLD:
            if self._lod_active:
                self.image_item.setPixmap(self._original_pixmap)
                self.image_item.setScale(1.0)
                self._lod_active = False
            return

        native_w, native_h = self._native_size.width(), self._native_size.height()
        # Resample to the true PHYSICAL pixel count, not just native*scale (which
        # is logical/device-independent only). QOpenGLWidget renders to physical
        # pixels, so a logical-only target leaves the GPU to upscale our already-
        # downsampled pixmap by devicePixelRatio -- a second blur pass stacked on
        # top of the resample, right at the threshold crossing where it's most
        # visible. setDevicePixelRatio() on the result tells Qt this pixmap
        # already matches the physical grid, so no further GPU scaling happens.
        dpr = self.devicePixelRatioF()
        target_w = max(1, round(native_w * scale * dpr))
        target_h = max(1, round(native_h * scale * dpr))

        current = self.image_item.pixmap()
        if self._lod_active and current.width() == target_w and current.height() == target_h:
            return  # already resampled to this exact size

        resampled = self._original_pixmap.scaled(
            target_w, target_h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation,
        )
        resampled.setDevicePixelRatio(dpr)
        self.image_item.setPixmap(resampled)
        device_independent_w = target_w / dpr
        self.image_item.setScale(native_w / device_independent_w)
        self._lod_active = True

    def wheelEvent(self, event):
        if event.angleDelta().y() == 0:
            event.ignore()
            return
        self._zoom_anchor_vp = event.position().toPoint()
        self._zoom_anchor_scene = self.mapToScene(self._zoom_anchor_vp)
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom_at(factor)
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MiddleButton:
            self._middle_press_pos = event.position().toPoint()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        elif event.button() == Qt.MiddleButton:
            if self._middle_press_pos is not None:
                delta = event.position().toPoint() - self._middle_press_pos
                if delta.manhattanLength() <= 6:
                    self.reset_zoom()
            self._middle_press_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # --- Drag & Drop Events ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path) and os.path.splitext(file_path)[1].lower() in (
                    ".png", ".jpg", ".jpeg", ".bmp", ".gif"
                ):
                    self.fileDropped.emit(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    # --- Image Handling ---
    def _show_pixmap(self, pixmap: QPixmap):
        self._original_pixmap = pixmap
        self._native_size = pixmap.size()
        self._lod_active = False
        self._lod_timer.stop()

        if self.zoom_locked:
            saved_transform = self.transform()
            saved_h = self.horizontalScrollBar().value()
            saved_v = self.verticalScrollBar().value()

        if self._hint_label:
            self._hint_label.hide()
        self.scene.clear()
        self.image_item = QGraphicsPixmapItem(pixmap)
        self.image_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.image_item)
        rect = self.image_item.boundingRect()
        pad = max(rect.width(), rect.height()) * 2
        self.scene.setSceneRect(rect.adjusted(-pad, -pad, pad, pad))

        if self.zoom_locked:
            self.setTransform(saved_transform)
            self.horizontalScrollBar().setValue(saved_h)
            self.verticalScrollBar().setValue(saved_v)
        elif self.fit_locked:
            self.fit_zoom()
        else:
            self.resetTransform()   # 1:1 (100%)
            self.centerOn(rect.center())
        self.viewport().update()
        self._schedule_lod_check()

    def load_image(self, path: str):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self._show_pixmap(pixmap)

    def load_image_from_pixmap(self, pixmap: QPixmap):
        self._show_pixmap(pixmap)

    def original_pixmap(self) -> QPixmap | None:
        return self._original_pixmap

    def reset_zoom(self):
        if self.image_item:
            self.resetTransform()
            self.centerOn(self.image_item.sceneBoundingRect().center())
            self._schedule_lod_check()

    def fit_zoom(self):
        if not self.image_item:
            return
        # sceneBoundingRect(), not boundingRect() — the item may currently be
        # holding a downscaled LOD pixmap with a compensating setScale(), and
        # sceneBoundingRect() is the one that stays pinned to native image size
        # regardless of that (boundingRect() is item-local and would be wrong).
        r = self.image_item.sceneBoundingRect()
        vw, vh = self.viewport().width(), self.viewport().height()
        scale = min(vw / r.width(), vh / r.height())
        self.resetTransform()
        self.scale(scale, scale)
        self.centerOn(r.center())
        self._schedule_lod_check()

    def set_wedge_overlay(self, text: str | None, corner: str = "bottom_left"):
        self._wedge_corner = corner
        if self._overlay_label is None:
            lbl = QLabel(self.viewport())
            lbl.setStyleSheet(
                "color: white; background-color: rgba(0,0,0,160);"
                " padding: 4px 10px; border-radius: 3px;"
                " font: bold 14px 'Courier New';"
            )
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
            lbl.hide()
            self._overlay_label = lbl
        if not text:
            self._overlay_label.hide()
            return
        self._overlay_label.setText(text)
        self._overlay_label.adjustSize()
        self._overlay_label.show()
        self._reposition_overlay()
        self._overlay_label.raise_()

    def _reposition_overlay(self):
        lbl = self._overlay_label
        if lbl is None:
            return
        margin = 12
        w, h  = lbl.width(), lbl.height()
        vw    = self.viewport().width()
        vh    = self.viewport().height()
        positions = {
            "bottom_left":  (margin,          vh - h - margin),
            "bottom_right": (vw - w - margin, vh - h - margin),
            "top_left":     (margin,          margin),
            "top_right":    (vw - w - margin, margin),
        }
        x, y = positions.get(self._wedge_corner, positions["bottom_left"])
        lbl.move(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_locked:
            self.fit_zoom()
        self._reposition_overlay()
        if self._hint_label and self._hint_label.isVisible():
            self._hint_label.setGeometry(
                0, 0, self.viewport().width(), self.viewport().height()
            )



# formerly workflow_cache.py

class WorkflowCache:
    """Manages caching of PNG workflow data with LRU eviction"""
    
    def __init__(self, max_size=50):
        self.cache = {}  # file_path -> parsed_workflow_json
        self.access_order = []  # Track usage for LRU
        self.max_size = max_size
    
    def get(self, file_path, parser_func=None):
        """Get workflow data, parse if not cached"""
        if file_path in self.cache:
            # Move to front (most recently used)
            self.access_order.remove(file_path)
            self.access_order.append(file_path)
            return self.cache[file_path]
        
        # Parse if parser provided and not in cache
        if parser_func:
            workflow_data = parser_func(file_path)
            self.put(file_path, workflow_data)
            return workflow_data
        
        return None
    
    def put(self, file_path, workflow_data):
        """Cache workflow data with LRU eviction"""
        # If cache full, remove least recently used
        if len(self.cache) >= self.max_size:
            lru_file = self.access_order.pop(0)
            del self.cache[lru_file]
        
        # Add new entry
        self.cache[file_path] = workflow_data
        self.access_order.append(file_path)
    
    def clear(self):
        self.cache.clear()
        self.access_order.clear()

