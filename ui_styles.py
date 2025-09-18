# ui_styles.py
from PySide6.QtWidgets import QGroupBox

def create_styled_groupbox(title, style_variant="default"):
    """Create a consistently styled QGroupBox"""
    group = QGroupBox(title)
    
    base_style = """
        QGroupBox {{
            border: 2px solid {border_color};
            border-radius: 6px;
            margin-top: 16px;
            padding: 8px;
            background: {bg_color};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 8px 0 8px;
            color: {text_color};
            background: {bg_color};
            font-weight: bold;
        }}
    """
    
    styles = {
        "default": {
            "border_color": "#333333",
            "bg_color": "#2a2a2a", 
            "text_color": "#ffffff"
        },
        "light": {
            "border_color": "#cccccc",
            "bg_color": "#f8f8f8",
            "text_color": "#333333"
        },
        "accent": {
            "border_color": "#4466cc",
            "bg_color": "#2a2a2a",
            "text_color": "#aaccff"
        }
    }
    
    style_data = styles.get(style_variant, styles["default"])
    group.setStyleSheet(base_style.format(**style_data))
    return group
