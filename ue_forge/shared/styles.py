"""
UI Styles for UE Forge.

Modern dark theme based on zinc color palette with cyan accents.
Matches the React/Tailwind reference design.
"""

# Color palette - zinc scale with cyan accent
COLORS = {
    # Backgrounds
    "bg_primary": "#09090b",      # zinc-950
    "bg_secondary": "#18181b",    # zinc-900
    "bg_tertiary": "#27272a",     # zinc-800
    "bg_hover": "#3f3f46",        # zinc-700
    "bg_input": "#09090b",        # zinc-950
    
    # Borders
    "border_default": "#27272a",  # zinc-800
    "border_hover": "#3f3f46",    # zinc-700
    "border_focus": "rgba(34, 211, 238, 0.5)",  # cyan-400/50
    
    # Text
    "text_primary": "#fafafa",    # zinc-50
    "text_secondary": "#d4d4d8",  # zinc-300
    "text_muted": "#a1a1aa",      # zinc-400
    "text_dim": "#71717a",        # zinc-500
    "text_placeholder": "#52525b", # zinc-600
    
    # Accent
    "accent_primary": "#22d3ee",  # cyan-400
    "accent_hover": "#67e8f9",    # cyan-300
    "accent_bg": "rgba(34, 211, 238, 0.2)",  # cyan-400/20
    "accent_bg_hover": "rgba(34, 211, 238, 0.3)",  # cyan-400/30
    
    # Status
    "success": "#34d399",         # emerald-400
    "success_bg": "rgba(52, 211, 153, 0.2)",
    "success_border": "rgba(52, 211, 153, 0.3)",
    "warning": "#fbbf24",         # amber-400
    "warning_bg": "rgba(251, 191, 36, 0.2)",
    "warning_border": "rgba(251, 191, 36, 0.3)",
    "error": "#f87171",           # red-400
    "error_bg": "rgba(248, 113, 113, 0.2)",
    "error_border": "rgba(248, 113, 113, 0.3)",
    "info": "#a1a1aa",            # zinc-400
}

# Font settings
FONTS = {
    "family": "Segoe UI, SF Pro Display, Ubuntu, sans-serif",
    "family_mono": "Cascadia Code, SF Mono, Consolas, monospace",
    "size_xs": "11px",
    "size_sm": "12px",
    "size_base": "13px",
    "size_lg": "14px",
    "size_xl": "16px",
    "size_2xl": "18px",
}

# Border radius
RADIUS = {
    "sm": "4px",
    "md": "6px",
    "lg": "8px",
    "xl": "12px",
    "full": "9999px",
}

# Spacing
SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "24px",
    "2xl": "32px",
}


def get_main_stylesheet() -> str:
    """Generate the main application stylesheet."""
    from .icons import get_indicator_icon_path
    
    # Generate indicator icon paths
    radio_unchecked = get_indicator_icon_path('radio_unchecked', COLORS['text_dim'])
    radio_unchecked_hover = get_indicator_icon_path('radio_unchecked', COLORS['text_muted'])
    radio_checked = get_indicator_icon_path('radio_checked', COLORS['accent_primary'], COLORS['accent_primary'])
    checkbox_unchecked = get_indicator_icon_path('checkbox_unchecked', COLORS['text_dim'])
    checkbox_unchecked_hover = get_indicator_icon_path('checkbox_unchecked', COLORS['text_muted'])
    checkbox_checked = get_indicator_icon_path('checkbox_checked', COLORS['accent_primary'], COLORS['accent_primary'])
    
    return f"""
        /* ===== GLOBAL ===== */
        * {{
            outline: none;
        }}
        
        QWidget {{
            background-color: {COLORS['bg_primary']};
            color: {COLORS['text_primary']};
            font-family: {FONTS['family']};
            font-size: {FONTS['size_base']};
        }}
        
        QWidget:focus {{
            outline: none;
        }}
        
        QMainWindow {{
            background-color: {COLORS['bg_primary']};
        }}
        
        /* ===== SCROLL BARS ===== */
        QScrollBar:vertical {{
            background: transparent;
            width: 14px;
            margin: 0;
            padding: 0 3px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS['bg_tertiary']};
            border-radius: 4px;
            min-height: 40px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLORS['bg_hover']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        
        QScrollBar:horizontal {{
            background: transparent;
            height: 14px;
            margin: 0;
            padding: 3px 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {COLORS['bg_tertiary']};
            border-radius: 4px;
            min-width: 40px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {COLORS['bg_hover']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        
        /* ===== LABELS ===== */
        QLabel {{
            background: transparent;
            color: {COLORS['text_primary']};
        }}
        
        /* ===== LINE EDIT ===== */
        QLineEdit {{
            background-color: {COLORS['bg_input']};
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['lg']};
            padding: 10px 12px;
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_sm']};
            selection-background-color: {COLORS['accent_primary']};
        }}
        QLineEdit:focus {{
            border-color: {COLORS['border_focus']};
        }}
        QLineEdit:disabled {{
            background-color: {COLORS['bg_tertiary']};
            color: {COLORS['text_muted']};
        }}
        
        /* ===== COMBO BOX ===== */
        QComboBox {{
            background-color: {COLORS['bg_input']};
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['lg']};
            padding: 10px 36px 10px 12px;
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_sm']};
            min-width: 150px;
        }}
        QComboBox:hover {{
            border-color: {COLORS['border_hover']};
        }}
        QComboBox:focus {{
            border-color: {COLORS['border_focus']};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 32px;
            subcontrol-origin: padding;
            subcontrol-position: right center;
        }}
        QComboBox::down-arrow {{
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiM3MTcxN2EiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJtNiA5IDYgNiA2LTYiLz48L3N2Zz4=);
            width: 12px;
            height: 12px;
            margin-right: 10px;
        }}
        QComboBox::down-arrow:hover {{
            image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNhMWExYWEiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJtNiA5IDYgNiA2LTYiLz48L3N2Zz4=);
        }}
        QComboBox QAbstractItemView {{
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['md']};
            padding: 4px;
            selection-background-color: {COLORS['bg_tertiary']};
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 8px 12px;
            border-radius: {RADIUS['sm']};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {COLORS['bg_tertiary']};
        }}
        
        /* ===== BUTTONS ===== */
        QPushButton {{
            background-color: transparent;
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['lg']};
            padding: 8px 16px;
            color: {COLORS['text_muted']};
            font-size: {FONTS['size_sm']};
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {COLORS['bg_tertiary']};
            border-color: {COLORS['border_hover']};
            color: {COLORS['text_secondary']};
        }}
        QPushButton:pressed {{
            background-color: {COLORS['bg_hover']};
        }}
        QPushButton:disabled {{
            color: {COLORS['text_dim']};
            border-color: {COLORS['border_default']};
        }}
        
        /* Primary button - cyan filled */
        QPushButton[class="primary"] {{
            background-color: {COLORS['accent_primary']};
            border: none;
            color: {COLORS['bg_primary']};
            font-weight: 600;
            padding: 10px 24px;
        }}
        QPushButton[class="primary"]:hover {{
            background-color: {COLORS['accent_hover']};
            color: {COLORS['bg_primary']};
        }}
        QPushButton[class="primary"]:disabled {{
            background-color: {COLORS['bg_tertiary']};
            color: {COLORS['text_dim']};
        }}
        
        /* Icon button */
        QPushButton[class="icon"] {{
            padding: 6px;
            min-width: 32px;
            max-width: 32px;
            min-height: 32px;
            max-height: 32px;
        }}
        
        /* Browse button */
        QPushButton[class="browse"] {{
            padding: 10px 12px;
            background-color: {COLORS['bg_tertiary']};
        }}
        
        /* ===== RADIO BUTTONS ===== */
        QRadioButton {{
            background: transparent;
            color: {COLORS['text_secondary']};
            font-size: {FONTS['size_sm']};
            spacing: 12px;
            padding: 8px 0px;
        }}
        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
        }}
        QRadioButton::indicator:unchecked {{
            image: url("{radio_unchecked}");
        }}
        QRadioButton::indicator:checked {{
            image: url("{radio_checked}");
        }}
        QRadioButton::indicator:unchecked:hover {{
            image: url("{radio_unchecked_hover}");
        }}
        
        /* ===== CHECK BOXES ===== */
        QCheckBox {{
            background: transparent;
            color: {COLORS['text_secondary']};
            font-size: {FONTS['size_sm']};
            spacing: 12px;
            padding: 6px 0px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
        }}
        QCheckBox::indicator:unchecked {{
            image: url("{checkbox_unchecked}");
        }}
        QCheckBox::indicator:checked {{
            image: url("{checkbox_checked}");
        }}
        QCheckBox::indicator:unchecked:hover {{
            image: url("{checkbox_unchecked_hover}");
        }}
        
        /* ===== TEXT EDIT (Console) ===== */
        QTextEdit, QPlainTextEdit {{
            background-color: {COLORS['bg_primary']};
            border: none;
            color: {COLORS['text_muted']};
            font-family: {FONTS['family_mono']};
            font-size: {FONTS['size_xs']};
            padding: 8px;
            selection-background-color: {COLORS['accent_bg']};
        }}
        
        /* ===== SPLITTER ===== */
        QSplitter::handle {{
            background-color: {COLORS['border_default']};
        }}
        QSplitter::handle:horizontal {{
            width: 1px;
        }}
        QSplitter::handle:vertical {{
            height: 1px;
        }}
        
        /* ===== PROGRESS BAR ===== */
        QProgressBar {{
            background-color: {COLORS['bg_secondary']};
            border: none;
            height: 4px;
        }}
        QProgressBar::chunk {{
            background-color: {COLORS['accent_primary']};
        }}
        
        /* ===== GROUP BOX ===== */
        QGroupBox {{
            background-color: rgba(24, 24, 27, 0.3);
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['lg']};
            margin-top: 16px;
            padding: 16px;
            padding-top: 32px;
        }}
        QGroupBox::title {{
            color: {COLORS['text_secondary']};
            font-size: {FONTS['size_sm']};
            font-weight: 500;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            left: 12px;
        }}
        
        /* ===== DIALOG ===== */
        QDialog {{
            background-color: {COLORS['bg_secondary']};
        }}
        
        /* ===== MESSAGE BOX ===== */
        QMessageBox {{
            background-color: {COLORS['bg_secondary']};
        }}
        QMessageBox QLabel {{
            color: {COLORS['text_primary']};
        }}
        
        /* ===== TOOL TIP ===== */
        QToolTip {{
            background-color: {COLORS['bg_tertiary']};
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['md']};
            color: {COLORS['text_primary']};
            padding: 6px 10px;
            font-size: {FONTS['size_xs']};
        }}
        
        /* ===== LIST VIEW ===== */
        QListView, QListWidget {{
            background-color: {COLORS['bg_primary']};
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['lg']};
            padding: 4px;
            outline: none;
        }}
        QListView::item, QListWidget::item {{
            padding: 10px 14px;
            border-radius: {RADIUS['md']};
            margin: 2px 0px;
        }}
        QListView::item:selected, QListWidget::item:selected {{
            background-color: {COLORS['bg_tertiary']};
        }}
        QListView::item:hover, QListWidget::item:hover {{
            background-color: rgba(39, 39, 42, 0.7);
        }}
        
        /* ===== MENU ===== */
        QMenu {{
            background-color: {COLORS['bg_secondary']};
            border: 1px solid {COLORS['border_default']};
            border-radius: {RADIUS['md']};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 8px 32px 8px 16px;
            border-radius: {RADIUS['sm']};
        }}
        QMenu::item:selected {{
            background-color: {COLORS['bg_tertiary']};
        }}
    """


def get_radio_card_style(checked: bool = False) -> str:
    """Get style for radio card container."""
    border_color = COLORS['accent_primary'] if checked else COLORS['border_default']
    bg_color = COLORS['accent_bg'] if checked else "transparent"
    return f"""
        QFrame {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: {RADIUS['lg']};
            padding: 0px;
        }}
        QFrame:hover {{
            border-color: {COLORS['border_hover'] if not checked else COLORS['accent_primary']};
        }}
    """
