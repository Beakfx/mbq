from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QPainter
from PySide6.QtCore import Qt, Signal
from PySide6.QtOpenGLWidgets import QOpenGLWidget
import os

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

    