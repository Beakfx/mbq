from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtCore import Qt
import os


class ImageCanvas(QGraphicsView):
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

    # --- Drag & Drop Events ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # Check if at least one is an image file
            for url in event.mimeData().urls():
                if os.path.splitext(url.toLocalFile())[-1].lower() in [".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                print(f"Dropped file: {file_path}")
                self.load_image(file_path)
                break

    # --- Image Handling ---
    def load_image(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f"Failed to load image: {path}")
            return

        # Clear old scene items
        self.scene.clear()

        # Add new pixmap item
        self.image_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.image_item)

        # Center image in view
        self.fitInView(self.image_item, Qt.KeepAspectRatio)
