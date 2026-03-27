"""
SVG Icons from Lucide icon set.
All icons are stored as SVG strings for easy coloring and scaling.
"""
import os
import tempfile
from pathlib import Path

# Base SVG wrapper - use format() to set size and color
_SVG_TEMPLATE = '''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'''

# Custom SVG templates for form controls (not using stroke template)
_RADIO_CHECKED = '''<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"><circle cx="9" cy="9" r="8" fill="none" stroke="{border}" stroke-width="2"/><circle cx="9" cy="9" r="4" fill="{fill}"/></svg>'''
_RADIO_UNCHECKED = '''<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"><circle cx="9" cy="9" r="8" fill="none" stroke="{border}" stroke-width="2"/></svg>'''
_CHECKBOX_CHECKED = '''<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"><rect x="1" y="1" width="16" height="16" rx="4" fill="none" stroke="{border}" stroke-width="2"/><rect x="5" y="5" width="8" height="8" rx="1" fill="{fill}"/></svg>'''
_CHECKBOX_UNCHECKED = '''<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"><rect x="1" y="1" width="16" height="16" rx="4" fill="none" stroke="{border}" stroke-width="2"/></svg>'''

# Cache for indicator icon paths
_indicator_icon_cache = {}


class Icons:
    """Collection of Lucide SVG icons."""

    # Icon paths (without SVG wrapper)
    PUZZLE = '<path d="M19.439 7.85c-.049.322.059.648.289.878l1.568 1.568c.47.47.706 1.087.706 1.704s-.235 1.233-.706 1.704l-1.611 1.611a.98.98 0 0 1-.837.276c-.47-.07-.802-.48-.968-.925a2.501 2.501 0 1 0-3.214 3.214c.446.166.855.497.925.968a.979.979 0 0 1-.276.837l-1.61 1.61a2.404 2.404 0 0 1-1.705.707 2.402 2.402 0 0 1-1.704-.706l-1.568-1.568a1.026 1.026 0 0 0-.877-.29c-.493.074-.84.504-1.02.968a2.5 2.5 0 1 1-3.237-3.237c.464-.18.894-.527.967-1.02a1.026 1.026 0 0 0-.289-.877l-1.568-1.568A2.402 2.402 0 0 1 1.998 12c0-.617.236-1.234.706-1.704L4.315 8.68a.979.979 0 0 1 .837-.276c.47.07.802.48.968.925a2.501 2.501 0 1 0 3.214-3.214c-.446-.166-.855-.497-.925-.968a.979.979 0 0 1 .276-.837l1.61-1.61a2.404 2.404 0 0 1 1.705-.707c.617 0 1.234.236 1.704.706l1.568 1.568c.23.23.556.338.877.29.493-.074.84-.504 1.02-.968a2.5 2.5 0 1 1 3.237 3.237c-.464.18-.894.527-.967 1.02Z"/>'

    ZAP = '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>'

    SETTINGS = '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'

    PLAY = '<polygon points="6 3 20 12 6 21 6 3"/>'

    FOLDER_OPEN = '<path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2"/>'

    FILE_CODE = '<path d="M10 12.5 8 15l2 2.5"/><path d="m14 12.5 2 2.5-2 2.5"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/>'

    REFRESH_CW = '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>'

    CHEVRON_RIGHT = '<path d="m9 18 6-6-6-6"/>'

    CHEVRON_LEFT = '<path d="m15 18-6-6 6-6"/>'

    CHEVRON_DOWN = '<path d="m6 9 6 6 6-6"/>'

    CHEVRON_UP = '<path d="m18 15-6-6-6 6"/>'

    ARROW_LEFT = '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>'

    UPLOAD = '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>'

    COPY = '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>'

    TRASH_2 = '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>'

    CLOCK = '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'

    LOADER_2 = '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>'

    CHECK_CIRCLE_2 = '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>'

    X_CIRCLE = '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>'

    ALERT_TRIANGLE = '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>'

    SEARCH = '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>'

    TERMINAL = '<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>'

    HARD_DRIVE = '<line x1="22" x2="2" y1="12" y2="12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><line x1="6" x2="6.01" y1="16" y2="16"/><line x1="10" x2="10.01" y1="16" y2="16"/>'

    PACKAGE = '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/>'

    WRENCH = '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>'

    GAMEPAD_2 = '<line x1="6" x2="10" y1="11" y2="11"/><line x1="8" x2="8" y1="9" y2="13"/><line x1="15" x2="15.01" y1="12" y2="12"/><line x1="18" x2="18.01" y1="10" y2="10"/><path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z"/>'

    FOLDER_SEARCH = '<circle cx="17" cy="17" r="3"/><path d="M10.7 20H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v4.1"/><path d="m21 21-1.5-1.5"/>'

    FOLDER_INPUT = '<path d="M2 9V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-1"/><path d="M2 13h10"/><path d="m9 16 3-3-3-3"/>'

    STAR = '<path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/>'

    STAR_OFF = '<path d="M8.34 8.34 2 9.27l5 4.87L5.82 21 12 17.77 18.18 21l-.59-3.43"/><path d="M18.42 12.76 22 9.27l-6.91-1L12 2l-1.44 2.91"/><line x1="2" x2="22" y1="2" y2="22"/>'

    # Window control icons
    MINUS = '<path d="M5 12h14"/>'

    SQUARE = '<rect width="18" height="18" x="3" y="3" rx="2"/>'

    MAXIMIZE_2 = '<polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" x2="14" y1="3" y2="10"/><line x1="3" x2="10" y1="21" y2="14"/>'

    X = '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>'

    # Sidebar / navigation icons
    HAMMER = '<path d="m15 12-8.373 8.373a1 1 0 1 1-3-3L12 9"/><path d="m18 15 4-4"/><path d="m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172V7l-2.26-2.26a6 6 0 0 0-4.202-1.756L9 2.96l.92.82A6.18 6.18 0 0 1 12 8.4V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5"/>'

    TYPE = '<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/>'

    LAYOUT_GRID = '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>'

    EYE = '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>'

    ARROW_RIGHT = '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>'

    HASH = '<line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/>'

    BRACES = '<path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1"/><path d="M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1"/>'

    @classmethod
    def get(cls, name: str, size: int = 24, color: str = "currentColor") -> str:
        """
        Get an icon SVG with specified size and color.

        Args:
            name: Icon name (uppercase, e.g., "PUZZLE", "PLAY")
            size: Icon size in pixels
            color: Stroke color

        Returns:
            SVG string
        """
        path = getattr(cls, name.upper(), None)
        if path is None:
            return ""
        return _SVG_TEMPLATE.format(size=size, color=color, path=path)

    @classmethod
    def get_pixmap(cls, name: str, size: int = 24, color: str = "#a1a1aa"):
        """
        Get an icon as QPixmap.

        Args:
            name: Icon name
            size: Icon size in pixels
            color: Stroke color (hex)

        Returns:
            QPixmap
        """
        from PySide6.QtGui import QPixmap, QPainter
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray, Qt

        svg_data = cls.get(name, size, color)
        if not svg_data:
            return QPixmap()

        renderer = QSvgRenderer(QByteArray(svg_data.encode()))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        return pixmap

    @classmethod
    def get_icon(cls, name: str, size: int = 24, color: str = "#a1a1aa"):
        """
        Get an icon as QIcon.

        Args:
            name: Icon name
            size: Icon size in pixels
            color: Stroke color (hex)

        Returns:
            QIcon
        """
        from PySide6.QtGui import QIcon
        pixmap = cls.get_pixmap(name, size, color)
        return QIcon(pixmap)


def get_indicator_icon_path(indicator_type: str, border_color: str, fill_color: str = None) -> str:
    """
    Get path to indicator icon for use in stylesheets.
    Creates SVG file in temp directory and caches path.

    Args:
        indicator_type: One of 'radio_checked', 'radio_unchecked', 'checkbox_checked', 'checkbox_unchecked'
        border_color: Border color (hex)
        fill_color: Fill color for checked state (hex), ignored for unchecked

    Returns:
        Path to SVG file (forward slashes for Qt stylesheet compatibility)
    """
    cache_key = f"{indicator_type}_{border_color}_{fill_color}"

    if cache_key in _indicator_icon_cache:
        return _indicator_icon_cache[cache_key]

    templates = {
        'radio_checked': _RADIO_CHECKED,
        'radio_unchecked': _RADIO_UNCHECKED,
        'checkbox_checked': _CHECKBOX_CHECKED,
        'checkbox_unchecked': _CHECKBOX_UNCHECKED,
    }

    template = templates.get(indicator_type)
    if not template:
        return ""

    svg_content = template.format(border=border_color, fill=fill_color or border_color)

    # Create temp directory for icons if needed
    temp_dir = Path(tempfile.gettempdir()) / "ue_forge_icons"
    temp_dir.mkdir(exist_ok=True)

    # Save SVG file
    svg_path = temp_dir / f"{cache_key.replace('#', '')}.svg"
    svg_path.write_text(svg_content)

    # Convert to forward slashes for Qt
    path_str = str(svg_path).replace("\\", "/")
    _indicator_icon_cache[cache_key] = path_str

    return path_str