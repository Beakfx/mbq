# Project: AI Image Viewer (Tkinter → Qt6 Migration)

## Current Implementation (Tkinter)
```python
# Key Characteristics
- Framework: ttkbootstrap + TkinterDnD
- Core Features:
  * Drag-and-drop image loading
  * Filmstrip with PIL thumbnails
  * Basic metadata display
  * Zoom/pan with mouse controls
- Limitations:
  * Performance with 100+ images
  * Manual reference management
  * No native GPU acceleration
```

## Target Qt6 Architecture
```mermaid
graph TB
  A[QMainWindow] --> B[QGraphicsView]
  A --> C[QSplitter]
  C --> D[QListView]    # Filmstrip
  C --> E[QTreeWidget]  # Metadata
  A --> F[QStatusBar]   # Image stats
```

## Key Porting Priorities
1. **Filmstrip Replacement**
   - `QListView` + `QStandardItemModel`
   - Deferred thumbnail loading
   - Persistent selection highlight

2. **Preview Pane**
   - `QGraphicsView` with:
     - OpenGL acceleration
     - Smooth zoom/pan
     - Pixel-perfect rendering

3. **Metadata System**
   - Nested `QTreeWidget`
   - EXIF/AI parameter parsing
   - Copy-paste support

## Feature Preservation List
| Tkinter Feature       | Qt6 Equivalent          |
|-----------------------|-------------------------|
| Drag-and-drop         | `QDragEnterEvent`       |
| Mouse wheel zoom      | `QWheelEvent` + `QTransform` |
| Thumbnail generation  | `QImageReader`          |
| Path display          | `QStatusBar`            |

## Code Snippets to Bring Along
```python
# Metadata extraction (keep logic)
def get_ai_parameters(image_path):
    with Image.open(image_path) as img:
        return img.text or {}
```

## Immediate Qt6 Advantages
- Automatic memory management
- HiDPI/retina support
- CSS-like styling via QSS
- Thread-safe signal/slots

## Starter Template Request
```python
# Desired starting point for Qt6 version:
# 1. Main window with splitter
# 2. Basic image loading
# 3. Filmstrip scaffold
# 4. Dark/light theme toggle
```

> **Note to Next AI:**  
> This user values:  
> - Precise imports verification  
> - Tested code samples  
> - Gradual feature migration  
> - Performance benchmarks