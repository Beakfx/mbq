from pathlib import Path
from datetime import datetime
from PySide6.QtGui import QImageReader


class ImageFolder:
    SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

    def __init__(self, folder_path, start_file=None):
        """
        folder_path: Path to scan for images
        start_file: optional file path to set as the initial index
        """
        self.folder_path = Path(folder_path)
        self.files = []
        self.index = 0

        self.scan_folder()

        # If a specific start file was given, set index to that
        if start_file:
            try:
                self.index = [f["path"] for f in self.files].index(str(Path(start_file)))
            except ValueError:
                pass  # if not found, just leave at 0

    def scan_folder(self):
        """Populate self.files with image metadata"""
        if not self.folder_path.exists():
            self.files = []
            return

        all_files = [
            f for f in self.folder_path.iterdir()
            if f.suffix.lower() in self.SUPPORTED_EXTS and f.is_file()
        ]

        self.files = []
        for f in sorted(all_files, key=lambda x: x.name.lower()):
            # Get basic info
            file_info = {
                "path": str(f),
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime),
                "chunks": {},  # placeholder for PNG/genAI metadata
            }

            # Sniff image dimensions without loading fully
            try:
                reader = QImageReader(str(f))
                if reader.canRead():
                    size = reader.size()
                    file_info["width"] = size.width()
                    file_info["height"] = size.height()
                else:
                    file_info["width"] = None
                    file_info["height"] = None
            except Exception as e:
                print(f"⚠️ Could not read image size for {f.name}: {e}")
                file_info["width"] = None
                file_info["height"] = None

            self.files.append(file_info)

        self.index = 0

    def current(self):
        if self.files:
            return self.files[self.index]
        return None

    def next(self):
        if not self.files:
            return None
        self.index = (self.index + 1) % len(self.files)
        return self.current()

    def prev(self):
        if not self.files:
            return None
        self.index = (self.index - 1) % len(self.files)
        return self.current()
