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
from PySide6.QtGui import QPainter
from ui_styles import create_styled_groupbox
import os
import sys

import helpers


class MetaViewApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer GL Layout")
        
        # --- 4:3 Optimized Window Size ---
        # Calculate for 1024x768 image + UI elements
        self.resize(1400, 900)  # Wider window to accommodate right sidebar
        
        self.folder_model = None
        self.image_cache = {}
        self.cache_size = 5

        # --- Design reference sizes for 4:3 ---
        self.design_canvas_w = 1024  # Target image width
        self.design_canvas_h = 768   # Target image height
        self.design_thumb_w = 120    # Thumbnail width
        self.design_thumb_h = 90     # Thumbnail height (4:3)
        
        self.scale_factor = 1.0

        # ---- Central Widget ----
        central = QWidget()
        self.setCentralWidget(central)

        # ---- Master Grid Layout ----
        self.main_layout = QGridLayout(central)
        self.main_layout.setContentsMargins(10, 20, 10, 20)
        self.main_layout.setSpacing(10)

        # Column weights - center area for image, right for metadata
        self.main_layout.setColumnStretch(0, 0)   # left aesthetic spacer (fixed)
        self.main_layout.setColumnStretch(1, 3)   # center image area (main content)
        self.main_layout.setColumnStretch(2, 1)   # right metadata panel (~1/4 width)
        self.main_layout.setRowStretch(0, 1)      # main row expands

        # --- Left Spacer (Aesthetic) ---
        self.left_spacer = QFrame()
        self.left_spacer.setFixedWidth(40)  # Small fixed width spacer
        self.left_spacer.setStyleSheet("background: transparent;")
        self.main_layout.addWidget(self.left_spacer, 0, 0)

        # --- Center Image Area ---
        self.center_group = QGroupBox("Image View")
        # Keep everything default Qt style, just make borders darker
        #self.center_group.setStyleSheet("QGroupBox { border: 2px solid red; }")
        self.center_group.setStyleSheet("""
            QGroupBox { 
                border: 2px solid #333333; 
                border-radius: 4px; 
                margin-top: 10px; 
            } 
            QGroupBox::title { 
                subcontrol-origin: margin; 
                subcontrol-position: top left; 
                left: 10px; 
                padding: 0 5px 0 5px; 
                background: palette(window); 
            }
        """)
#self.right_metadata.setStyleSheet("QGroupBox { border-color: #222222; }")        
        self.main_layout.addWidget(self.center_group, 0, 1)
        center_layout = QGridLayout(self.center_group)
        center_layout.setRowStretch(0, 5)  # image view (most space)
        center_layout.setRowStretch(1, 1)  # filmstrip
        center_layout.setRowStretch(2, 0)  # buttons
        center_layout.setColumnStretch(0, 1)

        # ---- Image Canvas ----
        self.image_view = ImageCanvas()
        self.image_view.fileDropped.connect(self.load_image_from_path)
        self.image_view.setMinimumSize(800, 600)  # 4:3 minimum
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
        self.thumb_scroll_area.setMinimumHeight(100)
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

        # --- Right Metadata Panel ---
        self.right_metadata = QGroupBox("Metadata")
        self.right_metadata.setMinimumWidth(300)  # ~1/4 of window width
        metadata_layout = QVBoxLayout(self.right_metadata)
        
        # Placeholder metadata content
        metadata_layout.addWidget(QLabel("File Information:"))
        self.file_info_label = QLabel("No image loaded")
        metadata_layout.addWidget(self.file_info_label)
        
        metadata_layout.addWidget(QLabel("AI Parameters:"))
        self.ai_params_label = QLabel("Waiting for image...")
        metadata_layout.addWidget(self.ai_params_label)
        
        metadata_layout.addStretch()  # Push content to top
        
        self.main_layout.addWidget(self.right_metadata, 0, 2)

        # ---- Connect Signals ----
        open_btn.clicked.connect(self.open_test_image)
        next_btn.clicked.connect(self.show_next_image)
        prev_btn.clicked.connect(self.show_prev_image)

        # Initialize after UI is built
        QTimer.singleShot(100, self.initialize_scale)

    def initialize_scale(self):
        """Initialize after UI is fully built"""
        self.update_scale_factor()
        if self.folder_model:
            self.populate_filmstrip()

    def update_scale_factor(self):
        """Calculate scale factor based on current image view size"""
        if not hasattr(self, "image_view"):
            return
            
        # Use only the image view's available space
        avail_w = self.image_view.width()
        avail_h = self.image_view.height()
        
        # Calculate scale based on maintaining 4:3 aspect ratio
        scale_w = avail_w / self.design_canvas_w
        scale_h = avail_h / self.design_canvas_h
        self.scale_factor = min(scale_w, scale_h)

    # --- Image Handling ---
    def load_image_from_path(self, file_path):
        folder = os.path.dirname(file_path)
        self.folder_model = ImageFolder(folder, start_file=file_path)
        self.image_cache.clear()

        current = self.folder_model.current()
        if current:
            print("Displaying:", current["name"])
            self.display_image(current["path"])
            self.update_metadata(current)  # Update metadata panel
        self.populate_filmstrip()
        self.preload_adjacent_images()

    def update_metadata(self, file_info):
        """Update the right metadata panel with file information"""
        self.file_info_label.setText(
            f"Name: {file_info['name']}\n"
            f"Size: {file_info['size']:,} bytes\n"
            f"Modified: {file_info['modified'].strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Placeholder for AI metadata (you'll replace this with real data)
        self.ai_params_label.setText(
            "Model: Stable Diffusion\n"
            "Size: 1024x768\n"
            "Steps: 20\n"
            "CFG: 7.5"
        )

    def display_image(self, path):
        """Display image from cache or load it"""
        if path in self.image_cache:
            self.image_view.load_image_from_pixmap(self.image_cache[path])
        else:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.image_cache[path] = pixmap
                self.image_view.load_image(path)

    def preload_adjacent_images(self):
        """Pre-load images around current index"""
        if not self.folder_model or not self.folder_model.files:
            return
            
        files = self.folder_model.files
        current_idx = self.folder_model.index
        
        for offset in range(-2, 3):
            if offset == 0:
                continue
            idx = (current_idx + offset) % len(files)
            path = files[idx]["path"]
            if path not in self.image_cache:
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    self.image_cache[path] = pixmap

    def show_next_image(self):
        if self.folder_model:
            current = self.folder_model.next()
            if current:
                self.display_image(current["path"])
                self.update_metadata(current)
                self.populate_filmstrip()
                self.preload_adjacent_images()

    def show_prev_image(self):
        if self.folder_model:
            current = self.folder_model.prev()
            if current:
                self.display_image(current["path"])
                self.update_metadata(current)
                self.populate_filmstrip()
                self.preload_adjacent_images()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.show_prev_image()
        else:
            self.show_next_image()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scale_factor()
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

        # Calculate square thumbnail size based on filmstrip height
        filmstrip_height = self.thumb_scroll_area.height()
        thumb_size = filmstrip_height - 20  # Allow for padding
        
        # Calculate how many thumbs can fit in available width
        available_width = self.thumb_scroll_area.width()
        max_thumbs = max(5, available_width // thumb_size)  # At least 5, more if space
        
        center_index = self.folder_model.index
        files = self.folder_model.files
        if not files:
            return

        # Show dynamic number of thumbs centered on current index
        half_thumbs = max_thumbs // 2
        start_idx = center_index - half_thumbs
        end_idx = center_index + half_thumbs + (1 if max_thumbs % 2 else 0)
        
        for idx in range(start_idx, end_idx):
            actual_idx = idx % len(files)
            file_path = files[actual_idx]["path"]

            # Create square thumbnail with black padding
            pix = QPixmap(file_path).scaled(
                thumb_size, thumb_size,
                Qt.KeepAspectRatio,  # Maintain aspect ratio
                Qt.SmoothTransformation
            )
            
            # Create black background square
            final_pix = QPixmap(thumb_size, thumb_size)
            final_pix.fill(Qt.black)
            
            # Center the image on the black square
            painter = QPainter(final_pix)
            x_offset = (thumb_size - pix.width()) // 2
            y_offset = (thumb_size - pix.height()) // 2
            painter.drawPixmap(x_offset, y_offset, pix)
            painter.end()

            lbl = QLabel()
            lbl.setPixmap(final_pix)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(thumb_size, thumb_size)
            
            # Highlight current image
            if actual_idx == center_index:
                lbl.setStyleSheet("border: 2px solid #22aa33;")
            else:
                lbl.setStyleSheet("border: 1px solid #444;")
            
            self.thumb_layout.addWidget(lbl)

    def open_test_image(self):
        path = "test.png"
        try:
            pixmap = helpers.load_image(path)
            meta = helpers.get_fake_metadata(path)
            print("Metadata:", meta)
        except FileNotFoundError as e:
            print(e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetaViewApp()
    window.show()
    sys.exit(app.exec())

