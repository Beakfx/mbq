# qt_template.py
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, 
    QVBoxLayout, QLabel, QScrollArea,
    QFileDialog
)
from PyQt6.QtCore import Qt, QDir

class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("New Qt Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Layout
        layout = QVBoxLayout()
        central.setLayout(layout)
        
        # Add your components here:
        self.preview = QLabel("Drag images here")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview)
        
        # Enable drops
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            print("Dropped:", url.toLocalFile())  # Start here in new chat

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern look
    window = ImageViewer()
    window.show()
    sys.exit(app.exec())