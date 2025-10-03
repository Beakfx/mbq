#mbq_functions.py 
#combines ImageFolder, ImageCanvas, WorkflowCache classes to single file.

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QPainter, QImageReader
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
    # Signal emitted when a valid file is dropped
    fileDropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Scene holds the content
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # Make background black
        self.setBackgroundBrush(Qt.black)

        # Enable drag & drop
        self.setAcceptDrops(True)

        # Disable scrollbars (optional)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Keep track of current image
        self.image_item: QGraphicsPixmapItem | None = None

        # Make them nice to look at
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        self.setViewport(QOpenGLWidget())  # Hardware-accelerated rendering

     # Enable keyboard focus for the canvas
        self.setFocusPolicy(Qt.StrongFocus)

    def keyPressEvent(self, event):
        """Forward arrow keys to main window for navigation"""
        if event.key() in (Qt.Key_Right, Qt.Key_Left):
            main_window = self.window()  # Get the actual main window, not just the immediate parent
            if main_window:
                main_window.keyPressEvent(event)
            event.accept()
        else:
            super().keyPressEvent(event)

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
    def load_image(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f"Failed to load image: {path}")
            return

        print(f"Original: {pixmap.width()}x{pixmap.height()}")
        print(f"Viewport: {self.viewport().width()}x{self.viewport().height()}")

        self.scene.clear()

        # Add the original pixmap without pre-scaling
        self.image_item = QGraphicsPixmapItem(pixmap)
        self.image_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.image_item)

        # Set scene rect to exact image size
        rect = self.image_item.boundingRect()
        self.scene.setSceneRect(rect)
        
        # Let fitInView handle all scaling consistently
        self.fitInView(rect, Qt.KeepAspectRatio)
        
        # Force update to ensure smooth rendering
        self.viewport().update()

#        print(f"Displayed scene rect: {rect.width()}x{rect.height()}")

    # ← ADD THIS NEW METHOD FOR CACHING
    def load_image_from_pixmap(self, pixmap):
        """Load already-loaded pixmap (for cache) - FIXED VERSION"""
        self.scene.clear()

        # Add the original pixmap without pre-scaling
        self.image_item = QGraphicsPixmapItem(pixmap)
        self.image_item.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.image_item)

        # Set scene rect to exact image size
        self.scene.setSceneRect(self.image_item.boundingRect())
        
        # Let fitInView handle the scaling (consistent with load_image)
        self.fitInView(self.image_item, Qt.KeepAspectRatio)
        
        # Force update
        self.viewport().update()
        
#        print(f"Cached image displayed at: {self.image_item.boundingRect().width()}x{self.image_item.boundingRect().height()}")



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

