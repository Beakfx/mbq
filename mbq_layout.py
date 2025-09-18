from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea
)
from PySide6.QtCore import Qt
from image_canvas import ImageCanvas
from image_folder import ImageFolder
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QTimer
import os
import sys

import helpers


class MetaViewApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer Layout")
        self.resize(1400, 900)
        self.folder_model = None
        
        # Image cache
        self.image_cache = {}  # Dictionary to cache loaded images
        self.cache_size = 5    # Number of images to keep cached

        # --- Design reference sizes (for proportional scaling) ---
        self.design_canvas_w = 672
        self.design_canvas_h = 504
        self.design_thumb_w = self.design_canvas_w // 5   # 134
        self.design_thumb_h = self.design_thumb_w * 3 // 4  # 100
        self.design_total_h = (
            self.design_canvas_h + self.design_thumb_h + 40 + 20 + 20
        )
        self.scale_factor = 1.0

        # ---- Central Widget ----
        central = QWidget()
        self.setCentralWidget(central)

        # ---- Master Grid Layout ----
        self.main_layout = QGridLayout(central)
        self.main_layout.setContentsMargins(10, 20, 30, 20)
        self.main_layout.setSpacing(10)

        # Column weights like Tkinter's columnconfigure
        self.main_layout.setColumnStretch(0, 0)   # left sidebar
        self.main_layout.setColumnStretch(1, 5)   # center area
        self.main_layout.setColumnStretch(2, 3)   # right panel future
        self.main_layout.setRowStretch(0, 1)      # main row expands

        # --- Left Sidebar ---
        self.left_margin_frame = QFrame()
        left_layout = QVBoxLayout(self.left_margin_frame)
        left_layout.addWidget(QLabel("Sidebar"))
        self.main_layout.addWidget(self.left_margin_frame, 0, 0)

        # --- Center Image Area ---
        self.center_group = QGroupBox("Image View and Controls")
        self.main_layout.addWidget(self.center_group, 0, 1)
        center_layout = QGridLayout(self.center_group)
        center_layout.setRowStretch(0, 5)  # image view
        center_layout.setRowStretch(1, 1)  # filmstrip
        center_layout.setRowStretch(2, 0)  # buttons
        center_layout.setRowStretch(3, 0)  # path display later
        center_layout.setColumnStretch(0, 1)

        # ---- Image Canvas Equivalent ----
        self.image_view = ImageCanvas()
        self.image_view.fileDropped.connect(self.load_image_from_path)
        center_layout.addWidget(self.image_view, 0, 0)

        # ---- Filmstrip Frame ----
        self.filmstrip_frame = QFrame()
        filmstrip_layout = QVBoxLayout(self.filmstrip_frame)

        # Top separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #252222;")
        filmstrip_layout.addWidget(sep)

        # Thumbnail scroller
        self.thumb_scroll_area = QScrollArea()
        self.thumb_scroll_area.setWidgetResizable(True)
        self.thumb_container = QWidget()
        self.thumb_layout = QHBoxLayout(self.thumb_container)
        self.thumb_scroll_area.setWidget(self.thumb_container)

        filmstrip_layout.addWidget(self.thumb_scroll_area)
        center_layout.addWidget(self.filmstrip_frame, 1, 0)

        # ---- Button Frame ----
        self.button_frame = QFrame()
        btn_layout = QHBoxLayout(self.button_frame)

        next_btn = QPushButton("Next Image")
        prev_btn = QPushButton("Previous Image")
        open_btn = QPushButton("Open Image")

        btn_layout.addWidget(next_btn)
        btn_layout.addWidget(prev_btn)
        btn_layout.addWidget(open_btn)

        center_layout.addWidget(self.button_frame, 2, 0)

        open_btn.clicked.connect(self.open_test_image)
        next_btn.clicked.connect(self.show_next_image)
        prev_btn.clicked.connect(self.show_prev_image)

        # REMOVED THE PROBLEMATIC LINE: self.resizeEvent(None)
        # Instead, use a timer to initialize after UI is fully built
        QTimer.singleShot(100, self.initialize_scale)

    def initialize_scale(self):
        """Initialize scale factor after UI is fully built"""
        self.update_scale_factor()
        if self.folder_model:
            self.populate_filmstrip()


    def update_scale_factor(self):
        """Calculate scale factor based on current sizes"""
        if not hasattr(self, "image_view") or not hasattr(self, "filmstrip_frame"):
            return
            
        # Current available width and height
        avail_w = self.image_view.width()
        avail_h = self.image_view.height()

        print(f"Available space for image: {avail_w}x{avail_h}")

        # Compute scale factors relative to design sizes
        scale_w = avail_w / self.design_canvas_w
        scale_h = avail_h / self.design_total_h
        self.scale_factor = min(scale_w, scale_h)
        print(f"Scale factor updated: {self.scale_factor}")


    # --- Example method using helpers ---
    def open_test_image(self):
        """
        Demo function: load a test image and print metadata.
        """
        path = "test.png"  # placeholder
        try:
            pixmap = helpers.load_image(path)
            meta = helpers.get_fake_metadata(path)
            print("Metadata:", meta)
        except FileNotFoundError as e:
            print(e)

    #load image with path        
    def load_image_from_path(self, file_path):
        folder = os.path.dirname(file_path)
        self.folder_model = ImageFolder(folder, start_file=file_path)
        
        # Clear cache when folder changes
        self.image_cache.clear()

        current = self.folder_model.current()
        if current:
            print("Displaying:", current["name"])
            self.display_image(current["path"])
        self.populate_filmstrip()
        self.preload_adjacent_images()

    # New method for displaying images
    def display_image(self, path):
        """Display image from cache or load it"""
        if path in self.image_cache:
            # Use cached pixmap
            print(f"Using cached image: {os.path.basename(path)}")
            self.image_view.load_image_from_pixmap(self.image_cache[path])
        else:
            # Load and cache
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.image_cache[path] = pixmap
                self.image_view.load_image(path)

    # New method for preloading
    def preload_adjacent_images(self):
        """Pre-load images around current index"""
        if not self.folder_model or not self.folder_model.files:
            return
            
        files = self.folder_model.files
        current_idx = self.folder_model.index
        
        # Pre-load 2 images on each side
        for offset in range(-2, 3):
            if offset == 0:
                continue  # Skip current (already loaded)
                
            idx = (current_idx + offset) % len(files)
            path = files[idx]["path"]
            
            if path not in self.image_cache:
                # Load into cache but don't display
                print(f"Pre-loading: {os.path.basename(path)}")
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    self.image_cache[path] = pixmap

    def show_next_image(self):
        if self.folder_model:
            current = self.folder_model.next()
            if current:
                self.display_image(current["path"])
                self.populate_filmstrip()
                self.preload_adjacent_images()

    def show_prev_image(self):
        if self.folder_model:
            current = self.folder_model.prev()
            if current:
                self.display_image(current["path"])
                self.populate_filmstrip()
                self.preload_adjacent_images()

    # Mouse wheel handler
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            # wheel scrolled up
            self.show_prev_image()
        else:
            # wheel scrolled down
            self.show_next_image()

        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scale_factor()
        # Rebuild thumbs at new scale
        if self.folder_model:
            self.populate_filmstrip()

    def populate_filmstrip(self):
        # Clear old thumbnails
        for i in reversed(range(self.thumb_layout.count())):
            item = self.thumb_layout.takeAt(i)
            if widget := item.widget():
                widget.deleteLater()

        if not self.folder_model:
            return

        # Scale design size by current factor
        thumb_w = max(64, int(self.design_thumb_w * self.scale_factor))
        thumb_h = max(48, int(self.design_thumb_h * self.scale_factor))

        # Show 5 thumbnails centered on current index
        center_index = self.folder_model.index
        files = self.folder_model.files
        if not files:
            return

        for offset in range(-2, 3):
            idx = (center_index + offset) % len(files)
            file_path = files[idx]["path"]

            pix = QPixmap(file_path).scaled(
                thumb_w, thumb_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            lbl = QLabel()
            lbl.setPixmap(pix)
            lbl.setAlignment(Qt.AlignCenter)

            self.thumb_layout.addWidget(lbl)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetaViewApp()
    window.show()
    sys.exit(app.exec())
