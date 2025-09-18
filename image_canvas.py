from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QPainter
from PySide6.QtCore import Qt, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget  # ← ADD THIS IMPORT
import os


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
        
        # ← ADD OPENGL ACCELERATION HERE
        self.setViewport(QOpenGLWidget())  # Hardware-accelerated rendering

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
                    print("Dropped:", file_path)
                    self.fileDropped.emit(file_path)   # 👈 hand off to parent
                    event.acceptProposedAction()
                    print("drop complete")
                    return
        event.ignore()

    # --- Image Handling ---
    def load_image(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f"Failed to load image: {path}")
            return

        print(f"Loaded pixmap: {pixmap.width()}x{pixmap.height()}  path={path}")

        self.scene.clear()

        # Compute target size = size of the viewport
        target_size = self.viewport().size()
        if not target_size.isValid():
            target_size = pixmap.size()  # fallback

        # Resample pixmap to fit viewport, with smooth filter
        scaled = pixmap.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Add new pixmap item
        self.image_item = QGraphicsPixmapItem(scaled)
        self.image_item.setPos(0, 0)
        self.scene.addItem(self.image_item)

        # Update scene rect to fit the scaled pixmap
        rect = self.image_item.boundingRect()
        self.scene.setSceneRect(rect)

        # Center the image
        self.fitInView(rect, Qt.KeepAspectRatio)
        self.viewport().update()

        print("image displayed")
    
    # ← ADD THIS NEW METHOD FOR CACHING
    def load_image_from_pixmap(self, pixmap):
        """Load already-loaded pixmap (for cache)"""
        self.scene.clear()

        # Compute target size = size of the viewport
        target_size = self.viewport().size()
        if not target_size.isValid():
            target_size = pixmap.size()  # fallback

        # Resample pixmap to fit viewport, with smooth filter
        scaled = pixmap.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Add new pixmap item
        self.image_item = QGraphicsPixmapItem(scaled)
        self.image_item.setPos(0, 0)
        self.scene.addItem(self.image_item)

        # Update scene rect to fit the scaled pixmap
        rect = self.image_item.boundingRect()
        self.scene.setSceneRect(rect)

        # Center the image
        self.fitInView(rect, Qt.KeepAspectRatio)
        self.viewport().update()

        print("image displayed from cache")

    