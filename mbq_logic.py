# metaview_logic.py
from PySide6.QtCore import Qt
from mbq_functions import ImageFolder
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import QFileDialog
from mbq_parser import digest_workflow, ImageMetadata

import os


class MetaViewLogicMixin:
    """All the behavior logic goes here - no UI creation"""

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.show_prev_image()
        else:
            self.show_next_image()

        event.accept()
        return super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.show_next_image()
            event.accept()
        elif event.key() == Qt.Key_Left:
            self.show_prev_image()
            event.accept()
        else:
            super().keyPressEvent(event)

    def initialize_scale(self):
        """Initialize after UI is fully built"""
        self.update_scale_factor()
        if self.folder_model:
            self.populate_filmstrip()

    def update_scale_factor(self):
        """Calculate scale factor based on current image view size"""
        if not hasattr(self, "image_view"):
            return

        avail_w = self.image_view.width()
        avail_h = self.image_view.height()

        scale_w = avail_w / self.design_canvas_w
        scale_h = avail_h / self.design_canvas_h
        self.scale_factor = min(scale_w, scale_h)

    def update_metadata(self, file_info):
        """Update metadata panel with file info and AI parameters"""

        self.file_name_value.setText(file_info['name'])
        if 'width' in file_info and 'height' in file_info:
            self.file_dim_value.setText(f"{file_info['width']} x {file_info['height']} px")
        else:
            self.file_dim_value.setText("—")
        self.file_size_value.setText(f"{file_info['size']:,} bytes")
        self.file_mod_value.setText(file_info['modified'].strftime('%Y-%m-%d %H:%M'))

        workflow_data = self.get_workflow_data(file_info['path'])

        if workflow_data and getattr(workflow_data, "trusted_workflow", False):
            md = workflow_data

            self.model_value.setText(md.model or "—")
            self.steps_value.setText(str(md.steps) if md.steps is not None else "—")

            sampler_bits = []
            if md.sampler:
                sampler_bits.append(md.sampler)
            if md.scheduler:
                sampler_bits.append(md.scheduler)
            self.sampler_value.setText(" / ".join(sampler_bits) if sampler_bits else "—")

            self.cfg_value.setText(str(md.cfg) if md.cfg is not None else "—")
            self.seed_value.setText(str(md.seed) if md.seed is not None else "—")

            prompt_text = (md.prompt or "").strip()
            neg_prompt_text = (md.negative_prompt or "").strip()

            if md.matched_saveimage_prefix:
                header = f"[trusted: {md.matched_saveimage_prefix}]"
                self.prompt_value.setText((header + "\n\n" + (prompt_text or "(no prompt found)")).strip())
            else:
                self.prompt_value.setText(prompt_text or "(no prompt found)")

            self.neg_prompt_value.setText(neg_prompt_text or "(no negative prompt found)")

        else:
            reason = getattr(workflow_data, "ambiguity_reason", None) or "No workflow data"
            self.model_value.setText("—")
            self.steps_value.setText("—")
            self.sampler_value.setText("—")
            self.cfg_value.setText("—")
            self.seed_value.setText("—")
            self.prompt_value.setText(reason)
            self.neg_prompt_value.setText("—")
            print(f"❌ {reason}")

    def load_image_from_path(self, file_path):
        folder = os.path.dirname(file_path)
        self.folder_model = ImageFolder(folder, start_file=file_path)
        self.image_cache.clear()

        current = self.folder_model.current()
        if current:
            print("Displaying:", current["name"])
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

        filmstrip_height = self.thumb_scroll_area.height()
        thumb_size = filmstrip_height - 20
        available_width = self.thumb_scroll_area.width()
        max_thumbs = max(5, available_width // thumb_size)

        center_index = self.folder_model.index
        files = self.folder_model.files
        if not files:
            return

        half_thumbs = max_thumbs // 2
        start_idx = center_index - half_thumbs
        end_idx = center_index + half_thumbs + (1 if max_thumbs % 2 else 0)

        for idx in range(start_idx, end_idx):
            actual_idx = idx % len(files)
            file_path = files[actual_idx]["path"]

            pix = QPixmap(file_path).scaled(
                thumb_size, thumb_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            final_pix = QPixmap(thumb_size, thumb_size)
            final_pix.fill(Qt.black)

            painter = QPainter(final_pix)
            x_offset = (thumb_size - pix.width()) // 2
            y_offset = (thumb_size - pix.height()) // 2
            painter.drawPixmap(x_offset, y_offset, pix)
            painter.end()

            lbl = QLabel()
            lbl.setPixmap(final_pix)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedSize(thumb_size, thumb_size)

            if actual_idx == center_index:
                lbl.setStyleSheet("border: 2px solid #22aa33;")
            else:
                lbl.setStyleSheet("border: 1px solid #444;")

            self.thumb_layout.addWidget(lbl)

    def open_image_file(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Open Image File")
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                self.load_image_from_path(file_path)


def get_image_metadata(file_path: str) -> ImageMetadata:
    try:
        return digest_workflow(file_path)
    except Exception as e:
        print(f"[mbq_logic] Metadata parse failed for {file_path}: {e}")
        md = ImageMetadata(file=file_path)
        md.parsed_ok = False
        md.trust_status = "error"
        md.ambiguity_reason = f"Metadata parse failed: {e}"
        return md
