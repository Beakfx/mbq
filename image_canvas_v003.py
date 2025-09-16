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

        # Disable scrollbar (optional)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Keep track of current image
        self.image_item: QGraphicsPixmapItem | None = None


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
                print("DropEvent got:", file_path)  # debug
                if os.path.isfile(file_path) and os.path.splitext(file_path)[1].lower() in (
                    ".png", ".jpg", ".jpeg", ".bmp", ".gif"
                ):
                    print("Dropped:", file_path)
                    if self.parent() and hasattr(self.parent(), "load_image_from_path"):
                        self.parent().load_image_from_path(file_path)

                    #self.load_image(file_path)
                    event.acceptProposedAction()
                    print("drop complete")
                    return
        event.ignore()


    # --- Image Handling ---
    # --- Image Handling ---
    def load_image(self, path: str):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f"Failed to load image: {path}")
            return

        print(f"Loaded pixmap: {pixmap.width()}x{pixmap.height()}  path={path}")

        # Clear old scene items
        self.scene.clear()

        # Add new pixmap item
        self.image_item = QGraphicsPixmapItem(pixmap)
        self.image_item.setPos(0, 0)
        self.scene.addItem(self.image_item)

        # Ensure the scene rect covers the item(s)
        rect = self.scene.itemsBoundingRect()
        print("Scene itemsBoundingRect:", rect)
        if rect.isNull():
            # defensive: if rect is empty something is odd — still set pixmap area
            rect = self.image_item.boundingRect()
            print("Using image_item.boundingRect() as rect:", rect)

        self.scene.setSceneRect(rect)

        # Fit the view to the scene rect (keep aspect ratio)
        try:
            self.fitInView(rect, Qt.KeepAspectRatio)
        except Exception as e:
            print("fitInView error:", e)

        # Force a repaint of the viewport
        self.viewport().update()

        print("image displayed")

        # If you still don't see the image after this, uncomment the
        # fallback below which defers fitInView until the event loop
        # has finished a layout pass (sometimes necessary on initial show).
        #
        # from PySide6.QtCore import QTimer
        # QTimer.singleShot(0, lambda: self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio))


