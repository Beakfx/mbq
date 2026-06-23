__version__ = "1.2.0"

import html as _html
import send2trash
import os
import re
import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QGroupBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QFileDialog, QScrollArea, QLineEdit,
)
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QPixmap, QPainter, QDrag, QColor, QIcon, QShortcut, QPalette, QKeySequence
from PySide6.QtCore import Qt, QTimer, QEvent, QUrl, QMimeData, qInstallMessageHandler
from mbq_functions import ImageCanvas, ImageFolder, WorkflowCache
from mbq_parser import get_png_metadata


_THUMB_SIZE    = 80   # filmstrip thumbnail size in px
_FILMSTRIP_MAX = 500  # max image thumbnails to load

# --- display colours ---
C_NODE_HEADER = "#7ec8e3"   # node class name — muted cyan
C_NODE_TITLE  = "#888888"   # (title) suffix — mid grey
C_PARAM_KEY   = "#c8b86e"   # param key      — low yellow
C_PARAM_VALUE = "#dddddd"   # param value    — near-white


_MBQ_KEY_LABELS = {"filter": "wedge list"}  # display-only rename, distinct from ComfyUI's own "filter" widgets


def _format_wedge_value(v) -> str:
    """Display a swept wedge value: bare int for whole numbers, 2dp for floats, str() otherwise."""
    if isinstance(v, (int, float)):
        return str(int(v)) if v == int(v) else f"{v:.2f}"
    return str(v)


def _format_node_block(entry: dict) -> str:
    ctype = entry["class_type"]
    title = entry["title"]
    params = entry["params"]

    h = _html.escape(ctype)
    if title and title.lower().replace(" ", "") != ctype.lower().replace(" ", ""):
        h += f' <span style="color:{C_NODE_TITLE};">({_html.escape(title)})</span>'

    lines = [f'<b style="color:{C_NODE_HEADER};">{h}</b>']
    for k, v in params.items():
        if isinstance(v, float):
            val = f"{v:g}"
        elif isinstance(v, list):
            r = repr(v)
            val = r[:60] + ("..." if len(r) > 60 else "")
        else:
            val = str(v)
        display_k = _MBQ_KEY_LABELS.get(k, k) if ctype.startswith("MBQWedge") else k
        ek = _html.escape(display_k)
        ev = _html.escape(val)
        lines.append(
            f'&nbsp;&nbsp;<span style="color:{C_PARAM_KEY};">{ek}:</span>'
            f' <span style="color:{C_PARAM_VALUE};">{ev}</span>'
        )

    return "<br>".join(lines)


def _build_display_text(nodes: list) -> str:
    if not nodes:
        return ""
    blocks = "<br><br>".join(_format_node_block(n) for n in nodes)
    return f"<html><body>{blocks}</body></html>"


def _is_preview_save(filename: str, saveimage_prefixes: list) -> bool:
    """Heuristic: True if filename doesn't look like a SaveImage output."""
    if re.search(r'_\d+_\.\w+$', filename):
        return False
    for prefix in saveimage_prefixes:
        if filename.startswith(prefix):
            return False
    return True


def _make_folder_pixmap(name: str, size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.black)
    p = QPainter(pix)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#c8823a"))
    tab_w  = size // 3
    tab_h  = size // 10
    body_y = size // 4
    body_h = size // 2
    p.drawRoundedRect(0, body_y, size, body_h, 3, 3)
    p.drawRoundedRect(0, body_y - tab_h, tab_w, tab_h + 4, 2, 2)
    p.setPen(QColor("#dddddd"))
    font = p.font()
    font.setPointSize(max(7, size // 9))
    p.setFont(font)
    label = name[:12] + ("…" if len(name) > 12 else "")
    text_y = body_y + body_h + 2
    text_h = size - text_y - 2
    p.drawText(0, text_y, size, text_h,
               Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, label)
    p.end()
    return pix


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


class MBQViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MBQ Viewer v{__version__}")
        self.workflow_cache = WorkflowCache(max_size=50)

        self.resize(1400, 900)

        self.folder_model = None
        self.image_cache = {}
        self.thumb_cache = {}
        self._undo_stack: list[list[str]] = []  # each entry is one delete action's batch of paths
        self._thumb_labels: list[QLabel] = []
        self._filmstrip_selection: set[int] = set()
        self._filmstrip_anchor: int | None = None

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
        self.center_group = QGroupBox("Image")
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
        self.center_layout = center_layout = QGridLayout(self.center_group)
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

        self.filmstrip_scroll = QScrollArea()
        self.filmstrip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.filmstrip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.filmstrip_scroll.setWidgetResizable(False)
        self.filmstrip_scroll.setFrameShape(QFrame.NoFrame)
        self.filmstrip_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #333; border-radius: 2px; }"
        )
        self.filmstrip_scroll.setMinimumHeight(_THUMB_SIZE + 24)

        self._filmstrip_inner = QWidget()
        self._filmstrip_inner.setFixedHeight(_THUMB_SIZE + 4)
        self.thumb_layout = QHBoxLayout(self._filmstrip_inner)
        self.thumb_layout.setContentsMargins(2, 2, 2, 2)
        self.thumb_layout.setSpacing(2)
        self.filmstrip_scroll.setWidget(self._filmstrip_inner)
        filmstrip_layout.addWidget(self.filmstrip_scroll)

        center_layout.addWidget(self.filmstrip_frame, 1, 0)

        # ---- Path / Count row ----
        _path_row = QWidget()
        _path_row_layout = QHBoxLayout(_path_row)
        _path_row_layout.setContentsMargins(0, 0, 0, 0)
        _path_row_layout.setSpacing(0)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(
            "color: #888; font-size: 11px; font-family: 'Courier New'; padding: 1px 4px;"
        )
        self.path_label = QLabel("")
        self.path_label.setStyleSheet(
            "color: #AAA; font-size: 11px; font-family: 'Courier New'; padding: 1px 4px;"
        )
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        _path_row_layout.addWidget(self.count_label)
        _path_row_layout.addWidget(self.path_label, 1)
        center_layout.addWidget(_path_row, 2, 0)
        self._path_row = _path_row

        # ---- Button Frame ----
        self.button_frame = QFrame()
        btn_layout = QHBoxLayout(self.button_frame)
        btn_layout.setContentsMargins(0, 2, 0, 2)

        up_btn   = QPushButton("↑ Up")
        open_btn = QPushButton("Open Image ")
        prev_btn = QPushButton("◀  Previous")
        next_btn = QPushButton("Next  ▶")

        btn_layout.addWidget(up_btn)
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(prev_btn)
        btn_layout.addWidget(next_btn)
        btn_layout.addSpacing(18)
        self.del_btn = QPushButton("Delete <Del>")
        self.del_btn.setStyleSheet(
            "QPushButton { color: #e06060; border: 1px solid #7a3333; padding: 2px 10px; }"
            "QPushButton:hover { background: #3a1a1a; color: #ff8080; }"
            "QPushButton:pressed { background: #4a2020; }"
        )
        self.del_btn.clicked.connect(self.delete_current_image)
        btn_layout.addWidget(self.del_btn)

        # ---- Status Bulbs ----
        btn_layout.addStretch()

        bulb_style = "color: #8d8d8d; font-size: 10px;"

        def _bulb_group(bulb, text):
            grp = QHBoxLayout()
            grp.setSpacing(4)
            lbl = QLabel(text)
            lbl.setStyleSheet(bulb_style)
            grp.addWidget(bulb)
            grp.addWidget(lbl)
            return grp

        self.bulb_wedge   = StatusBulb("Wedge node", on_color="#4499dd")
        self.bulb_zoom    = StatusBulb("Zoom Lock")
        self.bulb_fit     = StatusBulb("Fit Lock", on_color="#44ccaa")
        self.bulb_scroll  = StatusBulb("Scroll Freeze")
        self.bulb_uncomfy = StatusBulb("UnComfy")

        btn_layout.addLayout(_bulb_group(self.bulb_wedge,   "Wedge"))
        btn_layout.addLayout(_bulb_group(self.bulb_zoom,    "Zoom (Z)"))
        btn_layout.addLayout(_bulb_group(self.bulb_fit,     "Fit (F)"))
        btn_layout.addLayout(_bulb_group(self.bulb_scroll,  "Scroll (S)"))
        btn_layout.addLayout(_bulb_group(self.bulb_uncomfy, "UnComfy"))

        center_layout.addWidget(self.button_frame, 3, 0)

        # --- Right Workflow Panel ---
        self.right_metadata = QGroupBox("Workflow")
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

        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        search_lbl = QLabel("⌕")
        search_lbl.setStyleSheet("color: #888; font-size: 14px;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search workflow…")
        self.search_input.setStyleSheet(
            "QLineEdit { background: #1a1a1a; color: #ddd; border: 1px solid #444;"
            " border-radius: 3px; padding: 2px 6px; font-size: 9pt; }"
            "QLineEdit:focus { border-color: #666; }"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._search_workflow)
        search_row.addWidget(search_lbl)
        search_row.addWidget(self.search_input)
        metadata_vbox.addLayout(search_row)

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

        file_menu = menu_bar.addMenu("File")
        open_img_action = QAction("Open Image", self, shortcut="Ctrl+O")
        open_img_action.triggered.connect(self.open_image_file)
        file_menu.addAction(open_img_action)
        file_menu.addAction("Open Path", self.open_folder)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self, shortcut="Ctrl+Q")
        exit_action.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.addAction("Copy Image", self._copy_image)
        edit_menu.addAction("Copy Summary", self._copy_workflow)
        edit_menu.addAction("Copy Workflow", self._copy_prompt_json)
        edit_menu.addSeparator()
        self._restore_action = edit_menu.addAction("Restore Deleted\tCtrl+Z", self.undo_delete)

        view_menu = menu_bar.addMenu("View")
        refresh_action = QAction("Refresh", self, shortcut="F5")
        refresh_action.triggered.connect(self.refresh_folder)
        view_menu.addAction(refresh_action)
        view_menu.addSeparator()
        self._lock_zoom_action = QAction("Lock Zoom\tZ", self, checkable=True)
        self._lock_zoom_action.toggled.connect(self._on_zoom_lock_toggled)
        view_menu.addAction(self._lock_zoom_action)
        reset_zoom_action = QAction("Reset Zoom\tR", self)
        reset_zoom_action.triggered.connect(self._reset_zoom)
        view_menu.addAction(reset_zoom_action)
        self._fit_lock_action = QAction("Fit Lock\tF", self, checkable=True)
        self._fit_lock_action.toggled.connect(self._on_fit_lock_toggled)
        view_menu.addAction(self._fit_lock_action)
        view_menu.addSeparator()
        self._freeze_scroll_action = QAction("Freeze Scroll\tS", self, checkable=True)
        self._freeze_scroll_action.toggled.connect(
            lambda checked: self.bulb_scroll.set_state("on" if checked else "off")
        )
        view_menu.addAction(self._freeze_scroll_action)
        view_menu.addSeparator()
        self._fullscreen_action = QAction("Full Screen", self, checkable=True, shortcut="F11")
        self._fullscreen_action.toggled.connect(self._on_fullscreen_toggled)
        view_menu.addAction(self._fullscreen_action)
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
            act.triggered.connect(lambda checked, k=_key: self._set_wedge_corner(k))
            overlay_group.addAction(act)
            overlay_menu.addAction(act)

        about_menu = menu_bar.addMenu("About")
        about_menu.addAction("About MBQ…", self._show_about)
        about_menu.addAction("Help", self._open_help)

        # ---- Connect Signals ----
        up_btn.clicked.connect(self.navigate_up)
        open_btn.clicked.connect(self.open_image_file)
        next_btn.clicked.connect(self.show_next_image)
        prev_btn.clicked.connect(self.show_prev_image)
        copy_btn.clicked.connect(self._copy_workflow)
        self.copy_prompt_btn.clicked.connect(self._copy_prompt_json)

        self.installEventFilter(self)

        _sc_next = QShortcut(Qt.Key_Right, self)
        _sc_next.activated.connect(self.show_next_image)
        _sc_prev = QShortcut(Qt.Key_Left, self)
        _sc_prev.activated.connect(self.show_prev_image)
        QShortcut(Qt.Key_Delete, self).activated.connect(self.delete_current_image)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo_delete)
        QShortcut(Qt.Key_Escape, self).activated.connect(self._exit_fullscreen)

        # Redundant window-level shortcuts for the zoom/fit/scroll menu actions —
        # action shortcuts can stop firing once the menu bar is hidden (fullscreen),
        # so mirror the same direct-QShortcut pattern used for nav/delete above.
        QShortcut(QKeySequence("Z"), self).activated.connect(self._lock_zoom_action.toggle)
        QShortcut(QKeySequence("F"), self).activated.connect(self._fit_lock_action.toggle)
        QShortcut(QKeySequence("R"), self).activated.connect(self._reset_zoom)
        QShortcut(QKeySequence("S"), self).activated.connect(self._freeze_scroll_action.toggle)

        self.filmstrip_scroll.setFocusPolicy(Qt.NoFocus)

        zoom_timer = QTimer(self)
        zoom_timer.timeout.connect(self._update_zoom_readout)
        zoom_timer.start(150)

    # ---- Navigation ----

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

    def show_next_image(self):
        if self.folder_model:
            prev_idx = self.folder_model.index
            current = self.folder_model.next()
            if current:
                self.display_image(current["path"])
                self.update_metadata(current)
                self._scroll_to_current(prev_idx)
                self.preload_adjacent_images()

    def show_prev_image(self):
        if self.folder_model:
            prev_idx = self.folder_model.index
            current = self.folder_model.prev()
            if current:
                self.display_image(current["path"])
                self.update_metadata(current)
                self._scroll_to_current(prev_idx)
                self.preload_adjacent_images()

    def jump_to_index(self, idx):
        prev_idx = self.folder_model.index if self.folder_model else None
        self.folder_model.index = idx
        current = self.folder_model.current()
        if current:
            self.display_image(current["path"])
            self.update_metadata(current)
            self._scroll_to_current(prev_idx)
            self.preload_adjacent_images()

    def display_image(self, path):
        if path in self.image_cache:
            self.image_view.load_image_from_pixmap(self.image_cache[path])
        else:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.image_cache[path] = pixmap
                self.image_view.load_image(path)
        self.get_workflow_data(path)

    def preload_adjacent_images(self):
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

    # ---- Folder / file loading ----

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if folder:
            self.load_folder_from_path(folder)

    def open_image_file(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Open Image File")
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        if file_dialog.exec():
            selected = file_dialog.selectedFiles()
            if selected:
                self.load_image_from_path(selected[0])

    def load_folder_from_path(self, folder_path):
        self.folder_model = ImageFolder(folder_path)
        self.image_cache.clear()
        self.thumb_cache.clear()
        if self.folder_model.files:
            current = self.folder_model.current()
            self.display_image(current["path"])
            self.update_metadata(current)
        else:
            self._show_empty_folder()
        self.populate_filmstrip()
        self.preload_adjacent_images()
        self._update_path_label()

    def load_image_from_path(self, file_path):
        folder = os.path.dirname(file_path)
        self.folder_model = ImageFolder(folder, start_file=file_path)
        self.image_cache.clear()
        self.thumb_cache.clear()
        current = self.folder_model.current()
        if current:
            self.display_image(current["path"])
            self.update_metadata(current)
        self.populate_filmstrip()
        self.preload_adjacent_images()
        self._update_path_label()

    def refresh_folder(self):
        if not self.folder_model:
            return
        current = self.folder_model.current()
        current_path = current["path"] if current else None
        self.folder_model.scan_folder()
        if current_path:
            paths = [f["path"] for f in self.folder_model.files]
            if current_path in paths:
                self.folder_model.index = paths.index(current_path)
            else:
                self.folder_model.index = min(
                    self.folder_model.index, max(0, len(self.folder_model.files) - 1)
                )
        self.image_cache.clear()
        self.thumb_cache.clear()
        self.workflow_cache.clear()
        if self.folder_model.files:
            current = self.folder_model.current()
            self.display_image(current["path"])
            self.update_metadata(current)
        else:
            self._show_empty_folder()
        self.populate_filmstrip()
        self.preload_adjacent_images()
        self._update_path_label()

    def navigate_up(self):
        if not self.folder_model:
            return
        parent = self.folder_model.folder_path.parent
        if parent != self.folder_model.folder_path:
            self.load_folder_from_path(str(parent))

    def _on_fullscreen_toggled(self, checked):
        chrome = [self.left_spacer, self.right_metadata, self.filmstrip_frame,
                  self.button_frame, self._path_row]
        for w in chrome:
            w.setVisible(not checked)
        self.menuBar().setVisible(not checked)
        # Hidden widgets still reserve their grid stretch share, leaving the
        # canvas short of the window — zero those rows/columns out in fullscreen.
        self.main_layout.setColumnStretch(2, 0 if checked else 1)
        self.center_layout.setRowStretch(1, 0 if checked else 1)
        # In fullscreen: strip the QGroupBox border/title and outer layout margins
        # so the canvas truly fills edge-to-edge.
        if checked:
            # Cache inner layout defaults before zeroing them.
            m = self.center_layout.contentsMargins()
            self._cl_margins  = (m.left(), m.top(), m.right(), m.bottom())
            self._cl_spacing  = self.center_layout.spacing()
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)
            self.center_layout.setContentsMargins(0, 0, 0, 0)
            self.center_layout.setSpacing(0)
            self.center_group.setStyleSheet(
                "QGroupBox { border: none; margin: 0; padding: 0; }"
            )
            self.showFullScreen()
        else:
            self.main_layout.setContentsMargins(10, 20, 10, 20)
            self.main_layout.setSpacing(10)
            if hasattr(self, "_cl_margins"):
                self.center_layout.setContentsMargins(*self._cl_margins)
                self.center_layout.setSpacing(self._cl_spacing)
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
            self.showNormal()
        # showFullScreen()/showNormal() can leave the window without OS keyboard
        # focus on Windows, which makes shortcuts appear "broken" until clicked.
        self.activateWindow()
        self.image_view.setFocus(Qt.OtherFocusReason)

    def _exit_fullscreen(self):
        if self._fullscreen_action.isChecked():
            self._fullscreen_action.setChecked(False)

    def _update_path_label(self):
        if self.folder_model:
            n = len(self.folder_model.files)
            self.count_label.setText(f"{n} image{'s' if n != 1 else ''}:")
            self.path_label.setText(str(self.folder_model.folder_path))
        else:
            self.count_label.setText("")
            self.path_label.setText("")

    def _show_empty_folder(self):
        size = min(self.image_view.viewport().width(),
                   self.image_view.viewport().height()) // 2
        size = max(size, 120)
        pix = _make_folder_pixmap(self.folder_model.folder_path.name, size)
        self.image_view.load_image_from_pixmap(pix)
        self._clear_metadata_panel()

    def _clear_metadata_panel(self):
        """Reset the workflow panel, bulbs, and canvas overlay to their no-image state."""
        self.file_name_value.setText("—")
        self.file_name_value.setStyleSheet("")
        self.file_dim_value.setText("—")
        self.file_size_value.setText("—")
        self.file_mod_value.setText("—")
        self.primary_display.setPlainText("")
        self.tier3_display.setPlainText("")
        self.tier3_display.setVisible(False)
        self._tier3_count = 0
        self.tier3_btn.setVisible(False)
        self.bulb_uncomfy.set_state("off")
        self.bulb_wedge.set_state("off")
        self.copy_prompt_btn.setEnabled(False)
        self.image_view.set_wedge_overlay(None, getattr(self, "_wedge_corner", "bottom_left"))

    # ---- Metadata display ----

    def update_metadata(self, file_info):
        self.file_name_value.setText(file_info["name"])
        if "width" in file_info and "height" in file_info:
            self.file_dim_value.setText(f"{file_info['width']} x {file_info['height']} px")
        else:
            self.file_dim_value.setText("—")
        self.file_size_value.setText(f"{file_info['size']:,} bytes")
        self.file_mod_value.setText(file_info["modified"].strftime("%Y-%m-%d %H:%M"))

        md = self.get_workflow_data(file_info["path"])

        prefixes = md.get("saveimage_prefixes", []) if md else []
        is_preview = bool(md and prefixes and _is_preview_save(file_info["name"], prefixes))
        if is_preview:
            self.file_name_value.setStyleSheet("color: #c8823a;")
        else:
            self.file_name_value.setStyleSheet("")

        freeze = getattr(self._freeze_scroll_action, 'isChecked', lambda: False)()
        if freeze:
            sb = self.primary_display.verticalScrollBar()
            saved_scroll = sb.value() / sb.maximum() if sb.maximum() > 0 else 0.0
        else:
            saved_scroll = None

        tier3_was_open = self.tier3_display.isVisible()
        self.tier3_display.setVisible(False)

        wedge = md.get("wedge") if md else None
        wedge_val = wedge.get("current_value") if wedge else None

        if md and "tiers" in md:
            t1, t2, t3 = md["tiers"]

            # Pull MBQWedge out of wherever it naturally tiered, then place it:
            #   active sweep → tier 1 (it's the main thing you're reviewing)
            #   inactive / disconnected → tier 3 (still visible in plumbing, not hidden)
            is_mbq = lambda n: n.get("class_type", "").startswith("MBQWedge")
            mbq_nodes = [n for n in t1 + t2 + t3 if is_mbq(n)]
            t1 = [n for n in t1 if not is_mbq(n)]
            t2 = [n for n in t2 if not is_mbq(n)]
            t3 = [n for n in t3 if not is_mbq(n)]

            active_type = wedge.get("class_type") if wedge else None
            if wedge and wedge_val is not None and active_type:
                # Only the wedge node get_wedge_data actually matched gets its
                # display reformatted with the swept value — other wedge-type
                # nodes present in the graph (disconnected, or simply not the
                # active one) must not be stamped with a value that isn't theirs.
                active_nodes = [n for n in mbq_nodes if n.get("class_type") == active_type]
                other_nodes  = [n for n in mbq_nodes if n.get("class_type") != active_type]
                for node in active_nodes:
                    p = node["params"]
                    new_p = {}
                    if "parameter_name" in p:
                        new_p["parameter_name"] = p["parameter_name"]
                    new_p["current"] = _format_wedge_value(wedge_val)
                    new_p.update({k: v for k, v in p.items() if k != "parameter_name"})
                    node["params"] = new_p
                t1 = active_nodes + t1
                t3 = t3 + other_nodes
            else:
                t3 = t3 + mbq_nodes

            primary_html = _build_display_text(t1 + t2)
            if primary_html:
                if saved_scroll is not None:
                    self.primary_display.setUpdatesEnabled(False)
                self.primary_display.setHtml(primary_html)
                if saved_scroll is not None:
                    def _restore(frac=saved_scroll):
                        sb = self.primary_display.verticalScrollBar()
                        sb.setValue(int(sb.maximum() * frac))
                        self.primary_display.setUpdatesEnabled(True)
                    QTimer.singleShot(0, _restore)
            else:
                self.primary_display.setPlainText("(no ComfyUI params in this image)")
            self.tier3_display.setHtml(_build_display_text(t3))
            self._tier3_count = len(t3)
            if tier3_was_open and self._tier3_count > 0:
                self.tier3_display.setVisible(True)
                arrow = "▼"
            else:
                arrow = "▶"
            self.tier3_btn.setText(f'<span style="font-size:18px;">{arrow}</span> plumbing ({self._tier3_count} nodes)')
            self.tier3_btn.setVisible(self._tier3_count > 0)

            self.bulb_uncomfy.set_state("warn" if is_preview else "off")
            self.bulb_wedge.set_state("on" if wedge else "off")
            self.copy_prompt_btn.setEnabled(True)
        else:
            self.primary_display.setPlainText("(no ComfyUI metadata)")
            self.tier3_display.setPlainText("")
            self._tier3_count = 0
            self.tier3_btn.setVisible(False)
            self.bulb_uncomfy.set_state("warn")
            self.bulb_wedge.set_state("off")
            self.copy_prompt_btn.setEnabled(False)

        if self.search_input.text():
            QTimer.singleShot(0, lambda: self._search_workflow(self.search_input.text()))

        if wedge and wedge_val is not None:
            val_str = _format_wedge_value(wedge_val)
            overlay_text = f"{wedge['parameter_name']}: {val_str}"
        else:
            overlay_text = None
        self.image_view.set_wedge_overlay(overlay_text, getattr(self, "_wedge_corner", "bottom_left"))

    def toggle_tier3(self):
        visible = not self.tier3_display.isVisible()
        self.tier3_display.setVisible(visible)
        n = getattr(self, "_tier3_count", 0)
        arrow = "▼" if visible else "▶"
        self.tier3_btn.setText(f'<span style="font-size:18px;">{arrow}</span> plumbing ({n} nodes)')

    def _selected_file_infos(self):
        if not self.folder_model:
            return []
        return [
            self.folder_model.files[i]
            for i in sorted(self._filmstrip_selection)
            if 0 <= i < len(self.folder_model.files)
        ]

    def delete_current_image(self):
        if not self.folder_model or not self.folder_model.files:
            return
        targets = self._selected_file_infos()
        if len(targets) <= 1:
            current = self.folder_model.current()
            targets = [current] if current else []
        if not targets:
            return
        self._delete_images(targets)

    def _delete_images(self, file_infos):
        if len(file_infos) > 1:
            reply = QMessageBox.question(
                self, "Delete images",
                f"Move {len(file_infos)} images to the Recycle Bin / Trash?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        undoable_batch = []
        for file_info in file_infos:
            path = file_info["path"]
            try:
                send2trash.send2trash(path)
                undoable_batch.append(path)
            except send2trash.TrashPermissionError:
                reply = QMessageBox.warning(
                    self, "Cannot move to trash",
                    f"This file is on a network share or a filesystem that doesn't support trash.\n\n"
                    f"{file_info['name']}\n\n"
                    "Delete permanently? This cannot be undone.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    continue
                try:
                    os.remove(path)
                except Exception as e:
                    QMessageBox.warning(self, "Delete failed", str(e))
                    continue
            except Exception as e:
                QMessageBox.warning(self, "Delete failed", str(e))
                continue
            for key in [k for k in self.thumb_cache if k[0] == path]:
                del self.thumb_cache[key]
            self.folder_model.remove(path)

        if undoable_batch:
            self._undo_stack.append(undoable_batch)

        if self.folder_model.files:
            current = self.folder_model.current()
            self.display_image(current["path"])
            self.update_metadata(current)
        else:
            self._show_empty_folder()
        self.populate_filmstrip()
        self._update_path_label()

    def undo_delete(self):
        if not self._undo_stack:
            return
        batch = self._undo_stack.pop()
        restored = []
        failures = []
        for path in batch:
            try:
                self._restore_from_trash(path)
                restored.append(path)
            except Exception as e:
                failures.append((path, e))

        if failures:
            detail = "\n\n".join(
                f"{os.path.basename(p)}: {e}\nOriginal location: {p}" for p, e in failures
            )
            QMessageBox.information(
                self, "Undo",
                f"Could not restore {len(failures)} of {len(batch)} file(s) automatically. "
                f"They remain in your Recycle Bin / Trash.\n\n{detail}"
            )
        if not restored:
            return

        if self.folder_model:
            current_path = (self.folder_model.current() or {}).get("path")
            self.folder_model.scan_folder()
            if current_path:
                try:
                    self.folder_model.index = [f["path"] for f in self.folder_model.files].index(current_path)
                except ValueError:
                    pass
            try:
                idx = [f["path"] for f in self.folder_model.files].index(restored[-1])
                self.folder_model.index = idx
                current = self.folder_model.current()
                self.display_image(current["path"])
                self.update_metadata(current)
                self.populate_filmstrip()
            except ValueError:
                pass
        self._update_path_label()

    def _restore_from_trash(self, original_path: str):
        import shutil
        if sys.platform == "win32":
            import struct
            drive = os.path.splitdrive(original_path)[0] + "\\"
            recycle_root = os.path.join(drive, "$Recycle.Bin")
            if not os.path.exists(recycle_root):
                raise FileNotFoundError("Recycle Bin not found")
            for sid_entry in os.scandir(recycle_root):
                if not sid_entry.is_dir():
                    continue
                try:
                    for entry in os.scandir(sid_entry.path):
                        if not entry.name.upper().startswith("$I"):
                            continue
                        try:
                            with open(entry.path, "rb") as f:
                                data = f.read()
                            if len(data) < 24:
                                continue
                            version = struct.unpack_from("<q", data, 0)[0]
                            if version == 2:
                                path_len = struct.unpack_from("<i", data, 24)[0]
                                stored = data[28:28 + path_len * 2].decode("utf-16-le").rstrip("\x00")
                            else:
                                stored = data[24:].decode("utf-16-le").rstrip("\x00")
                            if stored.lower() == original_path.lower():
                                r_name = "$R" + entry.name[2:]
                                r_path = os.path.join(sid_entry.path, r_name)
                                if os.path.exists(r_path):
                                    shutil.move(r_path, original_path)
                                    os.remove(entry.path)
                                    return
                        except (OSError, UnicodeDecodeError, struct.error):
                            continue
                except OSError:
                    continue
            raise RuntimeError("File not found in Recycle Bin")
        elif sys.platform == "darwin":
            trash = os.path.expanduser("~/.Trash")
            name = os.path.basename(original_path)
            src = os.path.join(trash, name)
            if not os.path.exists(src):
                raise FileNotFoundError(f"{name} not found in Trash")
            shutil.move(src, original_path)
        else:
            import glob, urllib.parse, configparser
            uid = os.getuid()

            def _try_xdg_dir(trash_dir):
                for info_file in glob.glob(os.path.join(trash_dir, "info", "*.trashinfo")):
                    cp = configparser.ConfigParser()
                    cp.read(info_file)
                    stored = cp.get("Trash Info", "Path", fallback="")
                    if urllib.parse.unquote(stored) in (original_path, os.path.basename(original_path)):
                        base = os.path.splitext(os.path.basename(info_file))[0]
                        src = os.path.join(trash_dir, "files", base)
                        if os.path.exists(src):
                            shutil.move(src, original_path)
                            os.remove(info_file)
                            return True
                return False

            if _try_xdg_dir(os.path.expanduser("~/.local/share/Trash")):
                return
            parent_dev = os.stat(os.path.dirname(original_path)).st_dev
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    mount = parts[1]
                    try:
                        if os.stat(mount).st_dev == parent_dev:
                            for candidate in (
                                os.path.join(mount, f".Trash-{uid}"),
                                os.path.join(mount, ".Trash", str(uid)),
                            ):
                                if os.path.isdir(candidate) and _try_xdg_dir(candidate):
                                    return
                    except OSError:
                        continue
            raise FileNotFoundError(f"{os.path.basename(original_path)} not found in any trash location")

    def _search_workflow(self, text: str):
        from PySide6.QtGui import QTextCharFormat, QTextDocument, QTextCursor
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("#00aa44"))
        highlight_fmt.setForeground(QColor("#000000"))
        freeze = getattr(self._freeze_scroll_action, 'isChecked', lambda: False)()
        for display in (self.primary_display, self.tier3_display):
            if not text:
                display.setExtraSelections([])
                continue
            selections = []
            doc = display.document()
            cursor = doc.find(text, 0, QTextDocument.FindFlag(0))
            while not cursor.isNull():
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                sel.format = highlight_fmt
                selections.append(sel)
                cursor = doc.find(text, cursor)
            display.setExtraSelections(selections)
            if selections and not freeze and display is self.primary_display:
                jump = QTextCursor(selections[0].cursor)
                jump.clearSelection()
                display.setTextCursor(jump)

    # ---- Filmstrip ----

    def _thumb_border(self, idx, current_idx):
        if idx == current_idx:
            return "border: 2px solid #22aa33;"
        if idx in self._filmstrip_selection:
            return "border: 2px solid #2f6b3a;"
        return "border: 1px solid #444;"

    def _restyle_filmstrip(self):
        current_idx = self.folder_model.index if self.folder_model else -1
        for idx, lbl in enumerate(self._thumb_labels):
            lbl.setStyleSheet(self._thumb_border(idx, current_idx))

    def populate_filmstrip(self):
        self._filmstrip_selection.clear()
        self._filmstrip_anchor = None
        for i in reversed(range(self.thumb_layout.count())):
            item = self.thumb_layout.takeAt(i)
            if widget := item.widget():
                widget.deleteLater()
        self._thumb_labels = []

        if not self.folder_model:
            return

        # folder entries — all subdirs, no cap
        for subdir in (self.folder_model.subdirs or []):
            pix = _make_folder_pixmap(subdir.name, _THUMB_SIZE)
            lbl = QLabel()
            lbl.setPixmap(pix)
            lbl.setFixedSize(_THUMB_SIZE, _THUMB_SIZE)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("border: 1px solid #555;")
            lbl.setCursor(Qt.PointingHandCursor)
            lbl.setToolTip(subdir.name)
            path_str = str(subdir)
            lbl.mousePressEvent = lambda e, p=path_str: (
                self.load_folder_from_path(p) if e.button() == Qt.LeftButton else None
            )
            self.thumb_layout.addWidget(lbl)

        # image entries — linear, capped at _FILMSTRIP_MAX
        center_index = self.folder_model.index
        for actual_idx, file_info in enumerate(self.folder_model.files[:_FILMSTRIP_MAX]):
            file_path = file_info["path"]
            cache_key = (file_path, _THUMB_SIZE)
            if cache_key not in self.thumb_cache:
                pix = QPixmap(file_path).scaled(
                    _THUMB_SIZE, _THUMB_SIZE,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                final_pix = QPixmap(_THUMB_SIZE, _THUMB_SIZE)
                final_pix.fill(Qt.black)
                painter = QPainter(final_pix)
                painter.drawPixmap(
                    (_THUMB_SIZE - pix.width()) // 2,
                    (_THUMB_SIZE - pix.height()) // 2, pix
                )
                painter.end()
                self.thumb_cache[cache_key] = final_pix

            lbl = QLabel()
            lbl.setPixmap(self.thumb_cache[cache_key])
            lbl.setFixedSize(_THUMB_SIZE, _THUMB_SIZE)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(self._thumb_border(actual_idx, center_index))
            lbl.setCursor(Qt.PointingHandCursor)

            def _press(e, w=lbl):
                if e.button() == Qt.LeftButton:
                    w._drag_start = e.position().toPoint()

            def _move(e, path=file_path, w=lbl):
                if not (e.buttons() & Qt.LeftButton):
                    return
                start = getattr(w, '_drag_start', None)
                if start is None or (e.position().toPoint() - start).manhattanLength() < 8:
                    return
                w._drag_start = None
                drag = QDrag(w)
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(path)])
                drag.setMimeData(mime)
                px = w.pixmap().scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                drag.setPixmap(px)
                drag.setHotSpot(px.rect().center())
                drag.exec(Qt.CopyAction)

            def _release(e, idx=actual_idx, w=lbl):
                if e.button() == Qt.LeftButton:
                    start = getattr(w, '_drag_start', None)
                    if start is not None and (e.position().toPoint() - start).manhattanLength() < 8:
                        mods = e.modifiers()
                        if mods & Qt.ShiftModifier and self._filmstrip_anchor is not None:
                            lo, hi = sorted((self._filmstrip_anchor, idx))
                            self._filmstrip_selection = set(range(lo, hi + 1))
                        elif mods & Qt.ControlModifier:
                            self._filmstrip_selection.symmetric_difference_update({idx})
                            self._filmstrip_anchor = idx
                        else:
                            self._filmstrip_anchor = idx
                            self._filmstrip_selection = {idx}
                        self.jump_to_index(idx)
                        self._restyle_filmstrip()

            lbl.mousePressEvent   = _press
            lbl.mouseMoveEvent    = _move
            lbl.mouseReleaseEvent = _release
            self.thumb_layout.addWidget(lbl)
            self._thumb_labels.append(lbl)

        n = self.thumb_layout.count()
        total_w = 4 + n * _THUMB_SIZE + max(0, n - 1) * 2  # margins=4, spacing=2
        self._filmstrip_inner.resize(total_w, _THUMB_SIZE + 4)
        self._scroll_to_current()

    def _scroll_to_current(self, prev_idx=None):
        idx = self.folder_model.index if self.folder_model else -1
        if prev_idx is not None and 0 <= prev_idx < len(self._thumb_labels):
            self._thumb_labels[prev_idx].setStyleSheet(self._thumb_border(prev_idx, idx))
        if 0 <= idx < len(self._thumb_labels):
            lbl = self._thumb_labels[idx]
            lbl.setStyleSheet(self._thumb_border(idx, idx))
            QTimer.singleShot(0, lambda: self._ensure_visible(lbl))

    def _ensure_visible(self, lbl):
        """Scroll the filmstrip just enough to bring lbl into view — never recenters
        if it's already visible, so nonlinear selection doesn't yank the strip around."""
        sb = self.filmstrip_scroll.horizontalScrollBar()
        viewport_w = self.filmstrip_scroll.viewport().width()
        left, right = lbl.x(), lbl.x() + lbl.width()
        view_left = sb.value()
        view_right = view_left + viewport_w
        if left < view_left:
            sb.setValue(left)
        elif right > view_right:
            sb.setValue(right - viewport_w)

    # ---- Zoom / view ----

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

    def _set_wedge_corner(self, key):
        self._wedge_corner = key
        self.image_view._wedge_corner = key
        self.image_view._reposition_overlay()

    def _update_zoom_readout(self):
        pct = self.image_view.transform().m11() * 100
        self.file_zoom_value.setText(f"{round(pct / 5) * 5}%")

    # ---- Copy actions ----

    def _copy_image(self):
        pixmap = self.image_view.original_pixmap()
        if pixmap is not None:
            QApplication.clipboard().setPixmap(pixmap)

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

    # ---- About / help ----

    def _show_about(self):
        QMessageBox.about(
            self,
            "About MBQ",
            f"MBQ Viewer v{__version__}\n"
            "An OpenGL-accelerated image viewer built for ComfyUI workflows.\n\n"
            "Reads the prompt JSON embedded in PNG files by ComfyUI's SaveImage\n"
            "node and displays generation parameters — model, prompts, sampler,\n"
            "CFG, seed, steps — in a colour-coded side panel.\n\n"
            "MBQ Wedge\n"
            "Three companion ComfyUI nodes sweep a parameter across a range,\n"
            "queuing one job per value: MBQ Wedge (numeric — steps, CFG,\n"
            "guidance…), MBQ Wedge Sampler, and MBQ Wedge Scheduler. Each output\n"
            "PNG has its exact swept value embedded; MBQ overlays it on the\n"
            "canvas and highlights it in the metadata panel.\n\n"
            "Keyboard shortcuts\n"
            "  Ctrl+O    open image\n"
            "  ← / →     previous / next image\n"
            "  Delete    move image(s) to Recycle Bin / Trash\n"
            "  Ctrl+Z    restore last deleted image(s)\n"
            "  F5         refresh folder\n"
            "  Z          toggle zoom lock\n"
            "  F          toggle fit lock (auto-fit each image)\n"
            "  R          reset zoom (100%), clear locks\n"
            "  S          toggle scroll freeze\n"
            "  F11       enter / exit full screen\n"
            "  Esc       exit full screen\n"
            "  Ctrl+Q    quit\n\n"
            "github.com/Beakfx/mbq",
        )

    def _open_help(self):
        QDesktopServices.openUrl(QUrl(
            "https://github.com/Beakfx/mbq/blob/main/README.md#keyboard-shortcuts"
        ))

    # ---- Event filter ----

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if obj in (self.primary_display, self.tier3_display):
                obj.verticalScrollBar().setValue(
                    obj.verticalScrollBar().value() - event.angleDelta().y() // 4
                )
                return True
        return super().eventFilter(obj, event)

    # ---- Cache ----

    def get_workflow_data(self, file_path):
        return self.workflow_cache.get(file_path, get_png_metadata)


def _qt_message_filter(msg_type, context, message):
    # "drag leave received before drag enter" is a known-benign QGraphicsView
    # internal warning (Qt's own drag bookkeeping, not raised by our code) —
    # drop it so it doesn't spam stderr/the console on every drag-and-drop.
    if "drag leave received before drag enter" in message:
        return
    sys.stderr.write(message + "\n")


if __name__ == "__main__":
    qInstallMessageHandler(_qt_message_filter)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _p = QPalette()
    _p.setColor(QPalette.ColorRole.Window,          QColor(30, 30, 30))
    _p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    _p.setColor(QPalette.ColorRole.Base,            QColor(25, 25, 25))
    _p.setColor(QPalette.ColorRole.AlternateBase,   QColor(30, 30, 30))
    _p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(25, 25, 25))
    _p.setColor(QPalette.ColorRole.ToolTipText,     QColor(220, 220, 220))
    _p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    _p.setColor(QPalette.ColorRole.Button,          QColor(40, 40, 40))
    _p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    _p.setColor(QPalette.ColorRole.Highlight,       QColor(42, 130, 218))
    _p.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(_p)
    _base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    _icon_path = os.path.join(_base, "assets", "mbq_icon.ico")
    if os.path.exists(_icon_path):
        app.setWindowIcon(QIcon(_icon_path))
    window = MBQViewerApp()
    window.show()
    if len(sys.argv) > 1:
        if os.path.isfile(sys.argv[1]):
            QTimer.singleShot(0, lambda: window.load_image_from_path(sys.argv[1]))
        elif os.path.isdir(sys.argv[1]):
            QTimer.singleShot(0, lambda: window.load_folder_from_path(sys.argv[1]))
    sys.exit(app.exec())
