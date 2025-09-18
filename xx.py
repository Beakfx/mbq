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
from PySide6.QtCore import QTimer, QSize
import os
import sys

import helpers


class MetaViewApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer Layout")
        self.resize(800, 550)
        self.folder_model = None

        # --- Design reference sizes ---
        self.design_canvas_w = 672
        self.design_canvas_h = 504  # 4:3 aspect ratio
        self.design_thumb_w = 100   # Fixed thumbnail width
        self.design_thumb_h = 75    # 4:3 aspect ratio for thumbs
        
        self.scale_factor = 1.0

        # ---- Central Widget ----
        central = QWidget()
        self.setCentralWidget(central)

        # ---- Master Grid Layout ----
        self.main_layout = QGridLayout(central)
        self.main_layout.setContentsMargins(10, 20, 30, 40)
        self.main_layout.setSpacing(10)

        # Column weights
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
        center_layout.setSpacing(0)  # ← ZERO spacing between rows

        # Set row stretch factors - this is key for proper scaling
        center_layout.setRowStretch(0, 5)  # image view (most space)
        center_layout.setRowStretch(1, 1)  # filmstrip (less space)
        center_layout.setRowStretch(2, 0)  # buttons (fixed height)
        center_layout.setColumnStretch(0, 1)

        # ---- Image Canvas ----
        self.image_view = ImageCanvas()
        self.image_view.fileDropped.connect(self.load_image_from_path)
        self.image_view.setMinimumSize(400, 300)  # Minimum 4:3 size
        center_layout.addWidget(self.image_view, 0, 0)

        # ---- Filmstrip Frame ----
        self.filmstrip_frame = QFrame()
        filmstrip_layout = QVBoxLayout(self.filmstrip_frame)

        # REMOVE ALL SPACING AND MARGINS:
        filmstrip_layout.setSpacing(0)
        filmstrip_layout.setContentsMargins(0, 0, 0, 0)

        # Ultra-thin separator (or remove completely)
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #252222; border: none;")  # ← Optional: make border invisible
        sep.setFixedHeight(1)  # ← Only 1 pixel tall
        filmstrip_layout.addWidget(sep)

        # Thumbnail scroller - also remove any internal margins
        self.thumb_scroll_area = QScrollArea()
        self.thumb_scroll_area.setWidgetResizable(True)
        self.thumb_scroll_area.setMinimumHeight(80)  # ← Reduce minimum height
        self.thumb_scroll_area.setFrameShape(QFrame.NoFrame)  # ← Remove border if any

        self.thumb_container = QWidget()
        self.thumb_layout = QHBoxLayout(self.thumb_container)
        self.thumb_layout.setSpacing(0)  # ← No spacing between thumbnails
        self.thumb_layout.setContentsMargins(0, 0, 0, 0)  # ← No margins

        self.thumb_scroll_area.setWidget(self.thumb_container)
        filmstrip_layout.addWidget(self.thumb_scroll_area)

        center_layout.addWidget(self.filmstrip_frame, 1, 0)

        # ---- Button Frame ----
        self.button_frame = QFrame()
        btn_layout = QHBoxLayout(self.button_frame)
        btn_layout.setSpacing(10)

        next_btn = QPushButton("Next Image")
        prev_btn = QPushButton("Previous Image")
        open_btn = QPushButton("Open Image")

        btn_layout.addWidget(prev_btn)
        btn_layout.addWidget(next_btn)
        btn_layout.addWidget(open_btn)

        center_layout.addWidget(self.button_frame, 2, 0)

        open_btn.clicked.connect(self.open_test_image)
        next_btn.clicked.connect(self.show_next_image)
        prev_btn.clicked.connect(self.show_prev_image)

        # Set initial scale factor after UI is rendered
        QTimer.singleShot(100, self.update_scale_factor)

    def update_scale_factor(self):
        """Calculate scale factor based on current image view size"""
        if not hasattr(self, "image_view") or not self.image_view.width():
            return
            
        # Scale based on available width to maintain 4:3 aspect ratio
        available_width = self.image_view.width()
        self.scale_factor = available_width / self.design_canvas_w
        
        print(f"Scale factor updated: {self.scale_factor}")
        
        # Rebuild thumbs if folder is loaded
        if self.folder_model:
            self.populate_filmstrip()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scale_factor()

    # --- Rest of your methods remain the same ---
    def open_test_image(self):
        path = "test.png"
        try:
            pixmap = helpers.load_image(path)
            meta = helpers.get_fake_metadata(path)
            print("Metadata:", meta)
        except FileNotFoundError as e:
            print(e)

    def load_image_from_path(self, file_path):
        folder = os.path.dirname(file_path)
        self.folder_model = ImageFolder(folder, start_file=file_path)

        current = self.folder_model.current()
        if current:
            print("Displaying:", current["name"])
            self.image_view.load_image(current["path"])
        self.populate_filmstrip()

    def show_next_image(self):
        if self.folder_model:
            current = self.folder_model.next()
            if current:
                self.image_view.load_image(current["path"])
                self.populate_filmstrip()

    def show_prev_image(self):
        if self.folder_model:
            current = self.folder_model.prev()
            if current:
                self.image_view.load_image(current["path"])
                self.populate_filmstrip()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.show_prev_image()
        else:
            self.show_next_image()
        event.accept()

    def populate_filmstrip(self):
        # Clear old thumbnails
        for i in reversed(range(self.thumb_layout.count())):
            item = self.thumb_layout.takeAt(i)
            if widget := item.widget():
                widget.deleteLater()

        if not self.folder_model:
            return

        # Calculate thumbnail size based on scale factor
        thumb_w = max(64, int(self.design_thumb_w * self.scale_factor))
        thumb_h = max(48, int(self.design_thumb_h * self.scale_factor))
        
        print(f"Thumbnail size: {thumb_w}x{thumb_h}")

        # Show thumbnails centered on current index
        center_index = self.folder_model.index
        files = self.folder_model.files
        if not files:
            return

        for offset in range(-3, 4):
            idx = (center_index + offset) % len(files)
            file_path = files[idx]["path"]

            try:
                pix = QPixmap(file_path).scaled(
                    thumb_w, thumb_h,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                lbl = QLabel()
                lbl.setPixmap(pix)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFixedSize(thumb_w, thumb_h)
                
                # Highlight current image
                if idx == center_index:
                    lbl.setStyleSheet("border: 2px solid #339933;")
                else:
                    lbl.setStyleSheet("border: 1px solid gray;")
                
                self.thumb_layout.addWidget(lbl)
            except Exception as e:
                print(f"Error loading thumbnail {file_path}: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetaViewApp()
    window.show()
    sys.exit(app.exec())

