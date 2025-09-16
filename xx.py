from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QGraphicsView, QScrollArea, QScrollBar, QSplitter, QTabWidget,
    QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt
import sys


class MetaViewApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer Layout")
        self.resize(1200, 800)

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
        self.image_view = QGraphicsView()
        self.image_view.setStyleSheet("background-color: black;")
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
        btn_layout.addWidget(QPushButton("Next Image"))
        btn_layout.addWidget(QPushButton("Previous Image"))
        btn_layout.addWidget(QPushButton("Open Image"))
        center_layout.addWidget(self.button_frame, 2, 0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetaViewApp()
    window.show()
    sys.exit(app.exec())
