from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea
)
from PySide6.QtCore import Qt
from image_canvas import ImageCanvas
from image_folder import ImageFolder
import os
import sys

import helpers


class MetaViewApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer Layout")
        self.resize(1200, 700)
        self.folder_model = None

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
        center_layout.setRowStretch(0, 8)  # image view
        center_layout.setRowStretch(1, 0)  # filmstrip
        center_layout.setRowStretch(2, 0)  # buttons
        center_layout.setRowStretch(3, 0)  # path display later
        center_layout.setColumnStretch(0, 1)

        # ---- Image Canvas Equivalent ----
        self.image_view = ImageCanvas()
        self.image_view.fileDropped.connect(self.load_image_from_path)

        center_layout.addWidget(self.image_view, 0, 0)   # <-- missing before

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
        self.thumb_scroll_area.setMinimumHeight(150)  # experiment with value


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
            # (later you’ll display the pixmap inside image_view)
        except FileNotFoundError as e:
            print(e)

    #load image with path        
    def load_image_from_path(self, file_path):
        folder = os.path.dirname(file_path)
        self.folder_model = ImageFolder(folder, start_file=file_path)

        current = self.folder_model.current()
        if current:
            print("Displaying:", current["name"])
            self.image_view.load_image(current["path"])

    def show_next_image(self):
        if self.folder_model:
            current = self.folder_model.next()
            if current:
                self.image_view.load_image(current["path"])

    def show_prev_image(self):
        if self.folder_model:
            current = self.folder_model.prev()
            if current:
                self.image_view.load_image(current["path"])

    # Mouse wheel handler
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            # wheel scrolled up
            self.show_prev_image()
        else:
            # wheel scrolled down
            self.show_next_image()

        event.accept()




if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetaViewApp()
    window.show()
    sys.exit(app.exec())
