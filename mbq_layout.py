from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea
)
from image_canvas import ImageCanvas
from PySide6.QtCore import Qt, QTimer, QEvent
from png_parser import parse_png_workflow
from workflow_cache import WorkflowCache


import sys



from metaview_logic import MetaViewLogicMixin

class MetaViewApp(MetaViewLogicMixin, QMainWindow):
    # Now inherits from both QMainWindow and our logic mixin
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer GL Layout")
        self.workflow_cache = WorkflowCache(max_size=50)

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
        open_btn.clicked.connect(self.open_image_file)
        next_btn.clicked.connect(self.show_next_image)
        prev_btn.clicked.connect(self.show_prev_image)

        # Initialize after UI is built
        QTimer.singleShot(100, self.initialize_scale)


        # Install event filter on THIS window only
        self.installEventFilter(self)
            
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Right, Qt.Key_Left):
                result = self.keyPressEvent(event)
                return True  # Event handled, stop propagation
        return super().eventFilter(obj, event)

    def get_workflow_data(self, file_path):
        """Get workflow data using cache"""
        return self.workflow_cache.get(file_path, parse_png_workflow)
    
    def preload_workflows(self, file_paths):
        """Preload workflows for nearby images"""
        self.workflow_cache.preload_batch(file_paths, parse_png_workflow)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetaViewApp()
    window.show()
    sys.exit(app.exec())

