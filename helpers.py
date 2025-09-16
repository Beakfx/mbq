# helpers.py
from PySide6.QtGui import QPixmap

def load_image(path: str) -> QPixmap:
    """
    Load an image from disk and return a QPixmap.
    In the future, this can also handle scaling, caching, etc.
    """
    pixmap = QPixmap(path)
    if pixmap.isNull():
        raise FileNotFoundError(f"Could not load image: {path}")
    return pixmap


def get_fake_metadata(path: str) -> dict:
    """
    Temporary stub: returns fake metadata.
    Replace later with real EXIF/PNG chunk parsing.
    """
    return {
        "Filename": path,
        "Width": 1920,
        "Height": 1080,
        "Format": "PNG"
    }
