
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit,
)
from PySide6.QtGui import QAction
from mbq_functions import ImageCanvas
from PySide6.QtCore import Qt, QTimer, QEvent
from mbq_parser import get_png_metadata
from mbq_functions import WorkflowCache
from mbq_logic import MetaViewLogicMixin


import sys




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
        self.thumb_cache = {}
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
        self.right_metadata.setMinimumWidth(300)

        metadata_vbox = QVBoxLayout()
        metadata_vbox.setContentsMargins(8, 8, 8, 8)
        metadata_vbox.setSpacing(4)
        self.right_metadata.setLayout(metadata_vbox)

        label_style = "color: #888; font-size: 11px;"

        def style_label(lbl):
            lbl.setStyleSheet(label_style)
            return lbl

        # --- File Info (compact grid) ---
        self.file_name_label = style_label(QLabel("File:"))
        self.file_dim_label  = style_label(QLabel("Dimensions:"))
        self.file_size_label = style_label(QLabel("Size:"))
        self.file_mod_label  = style_label(QLabel("Modified:"))

        _sel = Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        self.file_name_value = QLabel("—")
        self.file_name_value.setTextInteractionFlags(_sel)
        self.file_dim_value  = QLabel("—")
        self.file_dim_value.setTextInteractionFlags(_sel)
        self.file_size_value = QLabel("—")
        self.file_size_value.setTextInteractionFlags(_sel)
        self.file_mod_value  = QLabel("—")
        self.file_mod_value.setTextInteractionFlags(_sel)

        file_grid = QGridLayout()
        file_grid.setHorizontalSpacing(8)
        file_grid.setVerticalSpacing(4)
        file_grid.setContentsMargins(0, 0, 0, 0)
        file_grid.addWidget(self.file_name_label, 0, 0)
        file_grid.addWidget(self.file_name_value, 0, 1)
        file_grid.addWidget(self.file_dim_label,  1, 0)
        file_grid.addWidget(self.file_dim_value,  1, 1)
        file_grid.addWidget(self.file_size_label, 2, 0)
        file_grid.addWidget(self.file_size_value, 2, 1)
        file_grid.addWidget(self.file_mod_label,  3, 0)
        file_grid.addWidget(self.file_mod_value,  3, 1)
        metadata_vbox.addLayout(file_grid)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333;")
        metadata_vbox.addWidget(sep)

        # --- Primary node display (tier 1 + tier 2) ---
        mono_style = "font-family: 'Courier New', 'Consolas', monospace; font-size: 9pt;"
        self.primary_display = QTextEdit()
        self.primary_display.setReadOnly(True)
        self.primary_display.setLineWrapMode(QTextEdit.WidgetWidth)
        self.primary_display.setStyleSheet(mono_style)
        metadata_vbox.addWidget(self.primary_display, stretch=1)

        # --- Tier 3 toggle + display ---
        self.tier3_btn = QPushButton("▶ plumbing")
        self.tier3_btn.setStyleSheet("text-align: left; padding: 2px 6px; font-size: 10px;")
        self.tier3_btn.setVisible(False)
        self.tier3_btn.clicked.connect(self.toggle_tier3)
        metadata_vbox.addWidget(self.tier3_btn)

        self.tier3_display = QTextEdit()
        self.tier3_display.setReadOnly(True)
        self.tier3_display.setLineWrapMode(QTextEdit.WidgetWidth)
        self.tier3_display.setStyleSheet(mono_style)
        self.tier3_display.setMaximumHeight(160)
        self.tier3_display.setVisible(False)
        metadata_vbox.addWidget(self.tier3_display)

        self.primary_display.installEventFilter(self)
        self.tier3_display.installEventFilter(self)

        # --- Copy button ---
        copy_btn = QPushButton("Copy Metadata")
        metadata_vbox.addWidget(copy_btn)

        # Add panel to main layout
        self.main_layout.addWidget(self.right_metadata, 0, 2)



        # ---- View Menu ----
        view_menu = self.menuBar().addMenu("View")
        self._lock_zoom_action = QAction("Lock Zoom", self, checkable=True, shortcut="Z")
        self._lock_zoom_action.toggled.connect(lambda checked: setattr(self.image_view, "zoom_locked", checked))
        view_menu.addAction(self._lock_zoom_action)

        # ---- Connect Signals ----
        open_btn.clicked.connect(self.open_image_file)
        next_btn.clicked.connect(self.show_next_image)
        prev_btn.clicked.connect(self.show_prev_image)

        # Initialize after UI is built
        QTimer.singleShot(100, self.initialize_scale)


        # Install event filter on THIS window only
        self.installEventFilter(self)

        def copy_metadata_to_clipboard():
            lines = [
                f"File: {self.file_name_value.text()}",
                f"Dimensions: {self.file_dim_value.text()}",
                f"Size: {self.file_size_value.text()}",
                f"Modified: {self.file_mod_value.text()}",
                "",
                self.primary_display.toPlainText(),
            ]
            t3 = self.tier3_display.toPlainText()
            if t3:
                lines += ["", "--- plumbing ---", t3]
            QApplication.clipboard().setText("\n".join(lines))


        copy_btn.clicked.connect(copy_metadata_to_clipboard)


            
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if obj in (self.primary_display, self.tier3_display):
                obj.verticalScrollBar().setValue(
                    obj.verticalScrollBar().value() - event.angleDelta().y() // 4
                )
                return True
        if event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Right, Qt.Key_Left):
                self.keyPressEvent(event)
                return True
        return super().eventFilter(obj, event)

    def get_workflow_data(self, file_path):
        return self.workflow_cache.get(file_path, get_png_metadata)

    def preload_workflows(self, file_paths):
        self.workflow_cache.preload_batch(file_paths, get_png_metadata)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MetaViewApp()
    window.show()
    if len(sys.argv) > 1:
        import os
        if os.path.isfile(sys.argv[1]):
            QTimer.singleShot(0, lambda: window.load_image_from_path(sys.argv[1]))
    sys.exit(app.exec())

