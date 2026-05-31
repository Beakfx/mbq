import html as _html
import os
import re

from PySide6.QtCore import Qt, QTimer, QMimeData, QUrl
from PySide6.QtGui import QPixmap, QPainter, QDrag
from PySide6.QtWidgets import QFileDialog, QLabel
from mbq_functions import ImageFolder
from mbq_parser import get_png_metadata


# --- display colours (tweak here) ---
C_NODE_HEADER = "#7ec8e3"   # node class name — muted cyan
C_NODE_TITLE  = "#888888"   # (title) suffix — mid grey
C_PARAM_KEY   = "#c8b86e"   # param key      — low yellow
C_PARAM_VALUE = "#dddddd"   # param value    — near-white


def _format_node_block(entry: dict) -> str:
    """Format one node entry as an HTML fragment."""
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
        ek = _html.escape(k)
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


class MetaViewLogicMixin:
    """All behavior logic — no UI creation."""

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.show_next_image()
            event.accept()
        elif event.key() == Qt.Key_Left:
            self.show_prev_image()
            event.accept()
        else:
            super().keyPressEvent(event)

    def update_metadata(self, file_info):
        """Update the metadata panel for the current image."""
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
            self.file_name_value.setStyleSheet("color: #c8823a;")  # amber — possible preview save
        else:
            self.file_name_value.setStyleSheet("")

        # Save scroll position as a fraction so it survives content height changes
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
            if wedge and wedge_val is not None:
                for node in mbq_nodes:
                    p = node["params"]
                    new_p = {}
                    if "parameter_name" in p:
                        new_p["parameter_name"] = p["parameter_name"]
                    new_p["current"] = str(int(wedge_val)) if wedge_val == int(wedge_val) else f"{wedge_val:.2f}"
                    new_p.update({k: v for k, v in p.items() if k != "parameter_name"})
                    node["params"] = new_p
                t1 = mbq_nodes + t1
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

        # Canvas overlay
        if wedge and wedge_val is not None:
            val_str = str(int(wedge_val)) if wedge_val == int(wedge_val) else f"{wedge_val:.2f}"
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

    def jump_to_index(self, idx):
        self.folder_model.index = idx
        current = self.folder_model.current()
        if current:
            self.display_image(current["path"])
            self.update_metadata(current)
            self.populate_filmstrip()
            self.preload_adjacent_images()

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
        current = self.folder_model.current()
        if current:
            self.display_image(current["path"])
            self.update_metadata(current)
        self.populate_filmstrip()
        self.preload_adjacent_images()

    def load_folder_from_path(self, folder_path):
        self.folder_model = ImageFolder(folder_path)
        self.image_cache.clear()
        self.thumb_cache.clear()
        current = self.folder_model.current()
        if current:
            self.display_image(current["path"])
            self.update_metadata(current)
        self.populate_filmstrip()
        self.preload_adjacent_images()

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

    def display_image(self, path):
        if path in self.image_cache:
            self.image_view.load_image_from_pixmap(self.image_cache[path])
        else:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.image_cache[path] = pixmap
                self.image_view.load_image(path)
        self.get_workflow_data(path)

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


    def populate_filmstrip(self):
        for i in reversed(range(self.thumb_layout.count())):
            item = self.thumb_layout.takeAt(i)
            if widget := item.widget():
                widget.deleteLater()

        if not self.folder_model:
            return

        filmstrip_height = self.thumb_area.height()
        thumb_size = filmstrip_height - 20
        available_width = self.thumb_area.width()
        max_thumbs = max(5, available_width // thumb_size)

        center_index = self.folder_model.index
        files = self.folder_model.files
        if not files:
            return

        num_files = len(files)
        if num_files <= max_thumbs:
            indices = list(range(num_files))
        else:
            half_thumbs = max_thumbs // 2
            start_idx = center_index - half_thumbs
            end_idx = center_index + half_thumbs + (1 if max_thumbs % 2 else 0)
            indices = [idx % num_files for idx in range(start_idx, end_idx)]

        for actual_idx in indices:
            file_path = files[actual_idx]["path"]

            cache_key = (file_path, thumb_size)
            if cache_key not in self.thumb_cache:
                pix = QPixmap(file_path).scaled(
                    thumb_size, thumb_size,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                final_pix = QPixmap(thumb_size, thumb_size)
                final_pix.fill(Qt.black)
                painter = QPainter(final_pix)
                painter.drawPixmap((thumb_size - pix.width()) // 2, (thumb_size - pix.height()) // 2, pix)
                painter.end()
                self.thumb_cache[cache_key] = final_pix
            final_pix = self.thumb_cache[cache_key]

            lbl = QLabel()
            lbl.setPixmap(final_pix)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(thumb_size, thumb_size)
            lbl.setStyleSheet("border: 2px solid #22aa33;" if actual_idx == center_index else "border: 1px solid #444;")
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
                        self.jump_to_index(idx)

            lbl.mousePressEvent   = _press
            lbl.mouseMoveEvent    = _move
            lbl.mouseReleaseEvent = _release
            self.thumb_layout.addWidget(lbl)

    def open_image_file(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Open Image File")
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        if file_dialog.exec():
            selected = file_dialog.selectedFiles()
            if selected:
                self.load_image_from_path(selected[0])
