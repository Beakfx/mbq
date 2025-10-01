

# metaview_logic.py
from PySide6.QtCore import Qt
from image_folder import ImageFolder
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFileDialog
from workflow_cache import WorkflowCache
from png_parser import parse_png_workflow, extract_prompt_info

import struct
import zlib
import os

class MetaViewLogicMixin:
    """All the behavior logic goes here - no UI creation"""
    

        # Mouse wheel handler
    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            # wheel scrolled up
            self.show_prev_image()
        else:
            # wheel scrolled down
            self.show_next_image()

        event.accept()
        return super().wheelEvent(event)  # ← FIXED: Only call super() once

    # arrow / key nav
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
        
        # Calculate scale based on maintaining 4:3 aspect ratio
        scale_w = avail_w / self.design_canvas_w
        scale_h = avail_h / self.design_canvas_h
        self.scale_factor = min(scale_w, scale_h)

    def update_metadata(self, file_info):
        """Update metadata panel with both file info and AI parameters."""
        # --- File info (always available) ---
        self.file_info_label.setText(
            f"Name: {file_info['name']}\n"
            f"Size: {file_info['size']:,} bytes\n"
            f"Modified: {file_info['modified'].strftime('%Y-%m-%d %H:%M')}"
        )

        print(f"🔄 update_metadata called for: {file_info['name']}")

        # --- Workflow / AI parameters ---
        workflow_data = self.get_workflow_data(file_info['path'])
        if workflow_data and "prompt_json" in workflow_data:
            prompt_info = extract_prompt_info(workflow_data["prompt_json"])
            
            # Build a readable string dynamically
            display_lines = []
            if prompt_info.get("model"):
                display_lines.append(f"Model: {prompt_info['model']}")
            if prompt_info.get("steps"):
                display_lines.append(f"Steps: {prompt_info['steps']}")
            if prompt_info.get("sampler"):
                display_lines.append(f"Sampler: {prompt_info['sampler']}")
            if prompt_info.get("cfg_scale"):
                display_lines.append(f"CFG/Guidance: {prompt_info['cfg_scale']}")
            if prompt_info.get("seed"):
                display_lines.append(f"Seed: {prompt_info['seed']}")
            if prompt_info.get("positive_prompt"):
                display_lines.append(f"Prompt: {prompt_info['positive_prompt'][:120]}...")

            # Show it in the metadata panel
            self.ai_params_label.setText("\n".join(display_lines))

            # Debug printout in console
            print("✅ Metadata extracted:")
            for line in display_lines:
                print("   " + line)

        else:
            print(f"❌ No workflow data for {file_info['name']}")
            self.ai_params_label.setText("No workflow data found")


        
    """ this old version of update_MD might come in handy
     def update_metadata(self, file_info):
        Update metadata panel - this should trigger workflow parsing
        # File info (always available)
        self.file_info_label.setText(
            f"Name: {file_info['name']}\n"
            f"Size: {file_info['size']:,} bytes\n"
            f"Modified: {file_info['modified'].strftime('%Y-%m-%d %H:%M')}"
        )
        
        print(f"🔄 update_metadata called for: {file_info['name']}")

        # AI parameters from workflow (this triggers parsing)
        workflow_data = self.get_workflow_data(file_info['path'])
        if workflow_data:
            print(f"✅ Workflow data FOUND for {file_info['name']}:")
            self.ai_params_label.setText(
                f"Model: {workflow_data.get('model', 'Unknown')}\n"
                f"Steps: {workflow_data.get('steps', '')}, Sampler: {workflow_data.get('sampler', '')}\n"
                f"CFG: {workflow_data.get('cfg_scale', '')}, Seed: {workflow_data.get('seed', '')}\n"
                f"Prompt: {workflow_data.get('positive_prompt', '')[:100]}..."
            )
        else:
            print(f"❌ No workflow data for {file_info['name']}")
            self.ai_params_label.setText("No workflow data found") """


    def load_image_from_path(self, file_path):
        folder = os.path.dirname(file_path)
        self.folder_model = ImageFolder(folder, start_file=file_path)
        self.image_cache.clear()

        current = self.folder_model.current()
        if current:
            print("Displaying:", current["name"])
            self.display_image(current["path"])


            # TEST: Parse and display workflow data
            self.test_workflow_parsing(current["path"])


            self.update_metadata(current)  # Update metadata panel
        self.populate_filmstrip()
        self.preload_adjacent_images()

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
            ###self.get_workflow_data(path)


    def display_image(self, path):
        """Display image from cache or load it"""
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

    def open_image_file(self):
        """Open file dialog to select an image"""
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Open Image File")
        file_dialog.setNameFilter("Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                file_path = selected_files[0]
                self.load_image_from_path(file_path)
    

    def test_workflow_parsing(self, file_path):
        """Test function to parse and display workflow data"""
        from png_parser import parse_png_workflow, extract_prompt_info
        
        print(f"\n🧪 TESTING WORKFLOW PARSING: {file_path}")
        workflow_data = parse_png_workflow(file_path)
        
        if workflow_data:
            print("✅ WORKFLOW DATA FOUND:")
            print("=" * 50)
            
            if 'prompt_json' in workflow_data:
                # Extract human-readable info
                prompt_info = extract_prompt_info(workflow_data['prompt_json'])
                print("\n🎨 EXTRACTED PROMPT INFO:")
                for key, value in prompt_info.items():
                    if value:  # Only show non-empty values
                        print(f"   {key}: {value}")
            
            if 'workflow_json' in workflow_data:
                print(f"\n📊 WORKFLOW JSON size: {len(str(workflow_data['workflow_json']))} chars")
            
            print("=" * 50)
        else:
            print("❌ No workflow data found")
        
        return workflow_data

    
    from png_parser import parse_png_workflow, extract_prompt_info




