#mbq_functions.py 
#combines ImageFolder, ImageCanvas, WorkflowCache classes to single file.

from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel,
)
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QPainter, QImageReader, QFont
from PySide6.QtCore import Qt, Signal
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
                "chunks": {},  # placeholder for PNG/genAI metadata
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
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setViewport(QOpenGLWidget())
        self.setFocusPolicy(Qt.StrongFocus)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)

        self.zoom_locked = False
        self._pan_start = None
        self._middle_press_pos = None
        self._zoom_anchor_vp = None
        self._zoom_anchor_scene = None
        self._overlay_label: QLabel | None = None
        self._wedge_corner: str = "bottom_left"

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
            print("drag enter")
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
                    self.fileDropped.emit(file_path)   # 👈 hand off to parent
                    event.acceptProposedAction()
                    return
        event.ignore()

    # --- Image Handling ---
    def _show_pixmap(self, pixmap: QPixmap):
        if self.zoom_locked:
            saved_transform = self.transform()
            saved_h = self.horizontalScrollBar().value()
            saved_v = self.verticalScrollBar().value()

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
        else:
            self.resetTransform()   # 1:1 (100%)
            self.centerOn(rect.center())
        self.viewport().update()

    def load_image(self, path: str):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self._show_pixmap(pixmap)

    def load_image_from_pixmap(self, pixmap: QPixmap):
        self._show_pixmap(pixmap)

    def reset_zoom(self):
        if self.image_item:
            self.resetTransform()
            self.centerOn(self.image_item.boundingRect().center())

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
        self._reposition_overlay()
        self._overlay_label.show()
        self._overlay_label.raise_()

    def _reposition_overlay(self):
        lbl = self._overlay_label
        if lbl is None or not lbl.isVisible():
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
        self._reposition_overlay()



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
    
    def preload_batch(self, file_paths, parser_func, max_preload=10):
        """Preload workflows for multiple files"""
        for file_path in file_paths[:max_preload]:
            if file_path not in self.cache:
                try:
                    workflow_data = parser_func(file_path)
                    self.put(file_path, workflow_data)
                except Exception as e:
                    print(f"Failed to preload workflow for {file_path}: {e}")
    
    def clear(self):
        """Clear the cache"""
        self.cache.clear()
        self.access_order.clear()
    
    def stats(self):
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'usage_ratio': len(self.cache) / self.max_size
        }

