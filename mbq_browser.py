
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QFileDialog,
)
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices
from PySide6.QtCore import Qt, QTimer, QEvent, QUrl
from mbq_functions import ImageCanvas, WorkflowCache
from mbq_parser import get_png_metadata
from mbq_logic import MetaViewLogicMixin

import sys


class StatusBulb(QLabel):
    _COLORS = {"on": "#44cc44", "warn": "#c8823a", "off": "#2a2a2a"}

    def __init__(self, tooltip_name, parent=None, on_color=None):
        super().__init__(parent)
        self._name = tooltip_name
        self._on_color = on_color
        self.setFixedSize(14, 14)
        self._state = "off"
        self._apply()

    def set_state(self, state: str):
        if state != self._state:
            self._state = state
            self._apply()

    def _apply(self):
        c = self._on_color if (self._state == "on" and self._on_color) else self._COLORS[self._state]
        self.setStyleSheet(f"background:{c}; border-radius:7px; border:1px solid #555;")
        self.setToolTip(f"{self._name}: {'ON' if self._state != 'off' else 'OFF'}")


class MetaViewApp(MetaViewLogicMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MBQ — Meta Browser")
        self.workflow_cache = WorkflowCache(max_size=50)

        self.resize(1400, 900)

        self.folder_model = None
        self.image_cache = {}
        self.thumb_cache = {}
        self.cache_size = 5

        self.design_canvas_w = 1024
        self.design_canvas_h = 768
        self.design_thumb_w = 120
        self.design_thumb_h = 90

        self.scale_factor = 1.0
        self._wedge_corner = "bottom_left"

        # ---- Central Widget ----
        central = QWidget()
        self.setCentralWidget(central)

        # ---- Master Grid Layout ----
        self.main_layout = QGridLayout(central)
        self.main_layout.setContentsMargins(10, 20, 10, 20)
        self.main_layout.setSpacing(10)

        self.main_layout.setColumnStretch(0, 0)
        self.main_layout.setColumnStretch(1, 3)
        self.main_layout.setColumnStretch(2, 1)
        self.main_layout.setRowStretch(0, 1)

        # --- Left Spacer ---
        self.left_spacer = QFrame()
        self.left_spacer.setFixedWidth(40)
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
        center_layout.setRowStretch(0, 5)
        center_layout.setRowStretch(1, 1)
        center_layout.setRowStretch(2, 0)
        center_layout.setColumnStretch(0, 1)

        # ---- Image Canvas ----
        self.image_view = ImageCanvas()
        self.image_view.fileDropped.connect(self.load_image_from_path)
        self.image_view.setMinimumSize(800, 600)
        center_layout.addWidget(self.image_view, 0, 0)

        # ---- Filmstrip Frame ----
        self.filmstrip_frame = QFrame()
        filmstrip_layout = QVBoxLayout(self.filmstrip_frame)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #252222;")
        filmstrip_layout.addWidget(sep)

        self.thumb_area = QFrame()
        self.thumb_area.setMinimumHeight(100)
        self.thumb_area.setStyleSheet("QFrame { border: 1px solid #333; border-radius: 2px; }")
        self.thumb_layout = QHBoxLayout(self.thumb_area)
        self.thumb_layout.setContentsMargins(0, 0, 0, 0)
        filmstrip_layout.addWidget(self.thumb_area)

        center_layout.addWidget(self.filmstrip_frame, 1, 0)

        # ---- Button Frame ----
        self.button_frame = QFrame()
        btn_layout = QHBoxLayout(self.button_frame)
        btn_layout.setContentsMargins(0, 2, 0, 2)

        next_btn = QPushButton("Next Image")
        prev_btn = QPushButton("Previous Image")
        open_btn = QPushButton("Open Image ")

        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(prev_btn)
        btn_layout.addWidget(next_btn)



        # ---- Status Bulbs ----
        btn_layout.addStretch()

        bulb_style = "color: #888; font-size: 10px;"

        def _bulb_group(bulb, text):
            grp = QHBoxLayout()
            grp.setSpacing(4)
            lbl = QLabel(text)
            lbl.setStyleSheet(bulb_style)
            grp.addWidget(bulb)
            grp.addWidget(lbl)
            return grp

        self.bulb_wedge  = StatusBulb("Wedge node", on_color="#4499dd")
        self.bulb_zoom   = StatusBulb("Zoom Lock")
        self.bulb_fit    = StatusBulb("Fit Lock", on_color="#44ccaa")
        self.bulb_scroll = StatusBulb("Scroll Freeze")
        self.bulb_uncomfy = StatusBulb("UnComfy")

        btn_layout.addLayout(_bulb_group(self.bulb_wedge,   "Wedge"))
        btn_layout.addLayout(_bulb_group(self.bulb_zoom,    "Zoom (Z)"))
        btn_layout.addLayout(_bulb_group(self.bulb_fit,     "Fit (F)"))
        btn_layout.addLayout(_bulb_group(self.bulb_scroll,  "Scroll (S)"))
        btn_layout.addLayout(_bulb_group(self.bulb_uncomfy, "UnComfy"))

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

        self.file_name_label = style_label(QLabel("File:"))
        self.file_dim_label  = style_label(QLabel("Dimensions:"))
        self.file_size_label = style_label(QLabel("Size:"))
        self.file_mod_label  = style_label(QLabel("Modified:"))
        self.file_zoom_label = style_label(QLabel("Zoom:"))

        _sel = Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
        self.file_name_value = QLabel("—")
        self.file_name_value.setTextInteractionFlags(_sel)
        self.file_dim_value  = QLabel("—")
        self.file_dim_value.setTextInteractionFlags(_sel)
        self.file_size_value = QLabel("—")
        self.file_size_value.setTextInteractionFlags(_sel)
        self.file_mod_value  = QLabel("—")
        self.file_mod_value.setTextInteractionFlags(_sel)
        self.file_zoom_value = QLabel("—")

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
        file_grid.addWidget(self.file_zoom_label, 4, 0)
        file_grid.addWidget(self.file_zoom_value, 4, 1)
        metadata_vbox.addLayout(file_grid)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #333;")
        metadata_vbox.addWidget(sep)

        mono_style = "font-family: 'Courier New', 'Consolas', monospace; font-size: 9pt;"
        self.primary_display = QTextEdit()
        self.primary_display.setReadOnly(True)
        self.primary_display.setLineWrapMode(QTextEdit.WidgetWidth)
        self.primary_display.setStyleSheet(mono_style)
        metadata_vbox.addWidget(self.primary_display, stretch=1)

        self.tier3_btn = QLabel()
        self.tier3_btn.setTextFormat(Qt.RichText)
        self.tier3_btn.setStyleSheet("padding: 2px 6px; font-size: 12px;")
        self.tier3_btn.setCursor(Qt.PointingHandCursor)
        self.tier3_btn.setVisible(False)
        self.tier3_btn.mousePressEvent = lambda _: self.toggle_tier3()
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

        copy_row = QHBoxLayout()
        copy_btn = QPushButton("Copy Summary")
        self.copy_prompt_btn = QPushButton("Copy Workflow")
        copy_row.addWidget(copy_btn)
        copy_row.addWidget(self.copy_prompt_btn)
        metadata_vbox.addLayout(copy_row)

        self.main_layout.addWidget(self.right_metadata, 0, 2)

        # ---- Menu Bar ----
        menu_bar = self.menuBar()

        # File
        file_menu = menu_bar.addMenu("File")
        open_img_action = QAction("Open Image", self, shortcut="Ctrl+O")
        open_img_action.triggered.connect(self.open_image_file)
        file_menu.addAction(open_img_action)
        file_menu.addAction("Open Path", self.open_folder)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self, shortcut="Ctrl+Q")
        exit_action.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(exit_action)

        # Edit
        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction("Copy Image", self._copy_image)
        edit_menu.addAction("Copy Summary", self._copy_workflow)
        edit_menu.addAction("Copy Workflow", self._copy_prompt_json)

        # View
        view_menu = menu_bar.addMenu("View")
        self._lock_zoom_action = QAction("Lock Zoom", self, checkable=True, shortcut="Z")
        self._lock_zoom_action.toggled.connect(self._on_zoom_lock_toggled)
        view_menu.addAction(self._lock_zoom_action)
        reset_zoom_action = QAction("Reset Zoom", self, shortcut="R")
        reset_zoom_action.triggered.connect(self._reset_zoom)
        view_menu.addAction(reset_zoom_action)
        self._fit_lock_action = QAction("Fit Lock", self, checkable=True, shortcut="F")
        self._fit_lock_action.toggled.connect(self._on_fit_lock_toggled)
        view_menu.addAction(self._fit_lock_action)
        view_menu.addSeparator()
        self._freeze_scroll_action = QAction("Freeze Scroll", self, checkable=True, shortcut="S")
        self._freeze_scroll_action.toggled.connect(
            lambda checked: self.bulb_scroll.set_state("on" if checked else "off")
        )
        view_menu.addAction(self._freeze_scroll_action)
        view_menu.addSeparator()
        overlay_menu = view_menu.addMenu("Wedge Overlay")
        overlay_group = QActionGroup(self)
        for _label, _key in [
            ("Bottom Left",  "bottom_left"),
            ("Bottom Right", "bottom_right"),
            ("Top Left",     "top_left"),
            ("Top Right",    "top_right"),
        ]:
            act = QAction(_label, self, checkable=True)
            act.setChecked(_key == "bottom_left")
            act.triggered.connect(lambda checked, k=_key: setattr(self, "_wedge_corner", k))
            overlay_group.addAction(act)
            overlay_menu.addAction(act)

        # About
        about_menu = menu_bar.addMenu("About")
        about_menu.addAction("About MBQ…", self._show_about)
        about_menu.addAction("Help", self._open_help)

        # ---- Connect Signals ----
        open_btn.clicked.connect(self.open_image_file)
        next_btn.clicked.connect(self.show_next_image)
        prev_btn.clicked.connect(self.show_prev_image)
        copy_btn.clicked.connect(self._copy_workflow)
        self.copy_prompt_btn.clicked.connect(self._copy_prompt_json)

        QTimer.singleShot(100, self.initialize_scale)
        self.installEventFilter(self)

        zoom_timer = QTimer(self)
        zoom_timer.timeout.connect(self._update_zoom_readout)
        zoom_timer.start(150)

    # ---- Menu handlers ----

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.load_folder_from_path(folder)

    def _on_zoom_lock_toggled(self, checked: bool):
        self.image_view.zoom_locked = checked
        self.bulb_zoom.set_state("on" if checked else "off")
        if checked:
            self._fit_lock_action.setChecked(False)

    def _on_fit_lock_toggled(self, checked: bool):
        self.image_view.fit_locked = checked
        self.bulb_fit.set_state("on" if checked else "off")
        if checked:
            self._lock_zoom_action.setChecked(False)
            self.image_view.fit_zoom()

    def _reset_zoom(self):
        self._lock_zoom_action.setChecked(False)
        self._fit_lock_action.setChecked(False)
        self.image_view.reset_zoom()

    def _copy_image(self):
        if self.image_view.image_item:
            QApplication.clipboard().setPixmap(self.image_view.image_item.pixmap())

    def _copy_prompt_json(self):
        if not self.folder_model:
            return
        current = self.folder_model.current()
        if not current:
            return
        md = self.get_workflow_data(current["path"])
        if not md:
            return
        # Prefer the workflow chunk (LiteGraph format ComfyUI loads natively).
        # Fall back to the prompt chunk serialised as JSON (API format).
        text = md.get("raw_workflow")
        if not text:
            import json
            raw = md.get("raw_prompt")
            if raw:
                text = json.dumps(raw, indent=2)
        if text:
            QApplication.clipboard().setText(text)

    def _copy_workflow(self):
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

    def _show_about(self):
        QMessageBox.about(
            self,
            "About MBQ",
            "MBQ — Meta Browser Qt\n"
            "An OpenGL-accelerated image viewer built for ComfyUI workflows.\n\n"
            "Reads the prompt JSON embedded in PNG files by ComfyUI's SaveImage\n"
            "node and displays generation parameters — model, prompts, sampler,\n"
            "CFG, seed, steps — in a colour-coded side panel.\n\n"
            "MBQ Wedge\n"
            "The companion ComfyUI node sweeps any numeric parameter (steps, CFG,\n"
            "guidance…) across a range, queuing one job per value. Each output PNG\n"
            "has its exact swept value embedded; MBQ overlays it on the canvas and\n"
            "highlights it in the metadata panel.\n\n"
            "Keyboard shortcuts\n"
            "  Ctrl+O    open image\n"
            "  ← / →     previous / next image\n"
            "  Z          toggle zoom lock\n"
            "  S          toggle scroll freeze\n"
            "  R          reset zoom (100%), clear locks\n"
            "  F          toggle fit lock (auto-fit each image)\n"
            "  Ctrl+Q    quit\n\n"
            "github.com/Beakfx/mbq",
        )

    def _open_help(self):
        QDesktopServices.openUrl(QUrl("https://github.com/Beakfx/mbq"))

    # ---- Event filter ----

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

    def _update_zoom_readout(self):
        pct = self.image_view.transform().m11() * 100
        self.file_zoom_value.setText(f"{round(pct / 5) * 5}%")

    # ---- Cache helpers ----

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
        elif os.path.isdir(sys.argv[1]):
            QTimer.singleShot(0, lambda: window.load_folder_from_path(sys.argv[1]))
    sys.exit(app.exec())
