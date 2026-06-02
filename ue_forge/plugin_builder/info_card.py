"""
Info card widget for displaying plugin information.
"""
from typing import Optional, List, Tuple
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt

from framekit.styles import COLORS, FONTS, RADIUS
from .types import PluginInfo
from framekit.localization import tr


class InfoRow(QWidget):
    """Single row of information with label and value."""

    def __init__(
            self,
            label: str,
            value: str,
            value_color: str = None,
            is_tag: bool = False,
            is_link: bool = False,
            parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"""
            color: {COLORS['text_dim']};
            font-size: {FONTS['size_sm']};
            background: transparent;
        """)
        label_widget.setMinimumWidth(100)
        layout.addWidget(label_widget)

        if is_tag and value:
            # Show as tag/badge
            tag_container = QWidget()
            tag_container.setStyleSheet("background: transparent;")
            tag_layout = QHBoxLayout(tag_container)
            tag_layout.setContentsMargins(0, 0, 0, 0)
            tag_layout.setSpacing(6)

            tags = value.split(", ") if ", " in value else [value]
            for tag_text in tags[:5]:  # Limit to 5 tags
                tag = QLabel(tag_text)
                color = value_color or COLORS['accent_primary']
                tag.setStyleSheet(f"""
                    background-color: rgba(34, 211, 238, 0.15);
                    color: {color};
                    font-size: {FONTS['size_xs']};
                    padding: 2px 8px;
                    border-radius: 4px;
                """)
                tag_layout.addWidget(tag)

            if len(tags) > 5:
                more = QLabel(f"+{len(tags) - 5}")
                more.setStyleSheet(f"""
                    color: {COLORS['text_dim']};
                    font-size: {FONTS['size_xs']};
                    background: transparent;
                """)
                tag_layout.addWidget(more)

            tag_layout.addStretch()
            layout.addWidget(tag_container, 1)
        elif is_link and value:
            # Show as clickable link
            value_widget = QLabel(f'<a href="{value}" style="color: {COLORS["accent_primary"]};">{value}</a>')
            value_widget.setOpenExternalLinks(True)
            value_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            value_widget.setStyleSheet(f"""
                font-size: {FONTS['size_sm']};
                font-family: {FONTS['family_mono']};
                background: transparent;
            """)
            value_widget.setWordWrap(True)
            layout.addWidget(value_widget, 1)
        else:
            value_widget = QLabel(value or "—")
            color = value_color or COLORS['text_secondary']
            value_widget.setStyleSheet(f"""
                color: {color};
                font-size: {FONTS['size_sm']};
                font-family: {FONTS['family_mono']};
                background: transparent;
            """)
            value_widget.setWordWrap(True)
            layout.addWidget(value_widget, 1)


class InfoSection(QWidget):
    """Section with title and rows."""

    def __init__(
            self,
            title: str,
            rows: List[Tuple],
            parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Section title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: {FONTS['size_xs']};
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: transparent;
            padding-bottom: 4px;
        """)
        layout.addWidget(title_label)

        # Rows
        for row_data in rows:
            label, value = row_data[0], row_data[1]
            color = row_data[2] if len(row_data) > 2 else None
            is_tag = row_data[3] if len(row_data) > 3 else False
            is_link = row_data[4] if len(row_data) > 4 else False
            row = InfoRow(label, value, color, is_tag, is_link)
            layout.addWidget(row)


class InfoCard(QWidget):
    """
    Card widget for displaying plugin information.
    
    Features:
    - Header with title
    - Scrollable content area
    - Multiple sections
    - Empty state placeholder (compact)
    - Expanded state when plugin loaded
    """
    
    # Heights for different states
    COMPACT_HEIGHT = 80  # When no plugin loaded (header + placeholder text)
    EXPANDED_HEIGHT = 280  # When plugin loaded
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "Plugin Information",
    ):
        super().__init__(parent)
        self._title = title
        self._content_widget: Optional[QWidget] = None
        self._is_expanded = False
        self.setMinimumHeight(self.COMPACT_HEIGHT)
        self.setMaximumHeight(self.COMPACT_HEIGHT)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main card frame
        self._card = QFrame()
        self._card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(24, 24, 27, 0.5);
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
        """)
        
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        
        # Header
        self._header = QFrame()
        self._header.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(39, 39, 42, 0.5);
                border: none;
                border-bottom: 1px solid {COLORS['border_default']};
                border-top-left-radius: {RADIUS['lg']};
                border-top-right-radius: {RADIUS['lg']};
            }}
        """)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: {FONTS['size_sm']};
            font-weight: 500;
            background: transparent;
        """)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()
        
        card_layout.addWidget(self._header)
        
        # Scroll area for content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Hidden in compact mode
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: transparent;
            }}
        """)
        
        # Content container
        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(16, 12, 16, 12)
        self._content_layout.setSpacing(16)
        
        # Empty state
        self._empty_label = QLabel(tr("no_information"))
        self._empty_label.setStyleSheet(f"""
            color: {COLORS['text_placeholder']};
            font-size: {FONTS['size_sm']};
            font-style: italic;
            background: transparent;
            border: none;
        """)
        self._content_layout.addWidget(self._empty_label)
        self._content_layout.addStretch()
        
        self._scroll.setWidget(self._content)
        card_layout.addWidget(self._scroll)
        
        layout.addWidget(self._card)

    def set_plugin_info(self, info: PluginInfo) -> None:
        """
        Set plugin information to display.

        Args:
            info: PluginInfo object with all plugin data
        """
        self.clear_items()
        self._empty_label.setVisible(False)

        # Expand card when plugin info is set
        self._set_expanded(True)

        # Container for all sections
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        sections_layout = QVBoxLayout(self._content_widget)
        sections_layout.setContentsMargins(0, 0, 0, 0)
        sections_layout.setSpacing(20)

        # === Basic Info Section ===
        basic_rows = [
            (tr("name"), info.friendly_name),
            (tr("version"), f"{info.version_name} (v{info.version})"),
            (tr("engine_version"), info.engine_version or "—"),
            (tr("category"), info.category or "—"),
            (tr("author"), info.created_by or "—"),
        ]
        if info.description:
            basic_rows.append((tr("description"), info.description))
        if info.parent_plugin_name:
            basic_rows.append((tr("parent_plugin"), info.parent_plugin_name))
        if info.editor_custom_virtual_path:
            basic_rows.append((tr("virtual_path"), info.editor_custom_virtual_path))

        basic_section = InfoSection(tr("section_basic"), basic_rows)
        sections_layout.addWidget(basic_section)

        # === Modules Section ===
        if info.modules:
            module_names = ", ".join([m.name for m in info.modules])
            module_types = ", ".join(list(set(m.type for m in info.modules)))

            module_rows = [
                (tr("modules"), f"{len(info.modules)}", None, False),
                (tr("module_types"), module_types, COLORS['accent_primary'], True),
                (tr("module_names"), module_names, None, False),
            ]

            modules_section = InfoSection(tr("section_modules"), module_rows)
            sections_layout.addWidget(modules_section)

        # === Dependencies Section ===
        if info.plugins:
            deps = ", ".join([p.name for p in info.plugins if p.enabled])
            optional_deps = ", ".join([p.name for p in info.plugins if p.optional])

            dep_rows = [
                (tr("dependencies"), deps if deps else "—", None, True if deps else False),
            ]
            if optional_deps:
                dep_rows.append((tr("optional_deps"), optional_deps, COLORS['text_dim'], True))

            deps_section = InfoSection(tr("section_dependencies"), dep_rows)
            sections_layout.addWidget(deps_section)

        # === Platforms Section ===
        if info.supported_platforms or info.supported_programs:
            platform_rows = []
            if info.supported_platforms:
                platforms = ", ".join(info.supported_platforms)
                platform_rows.append((tr("platforms"), platforms, COLORS['success'], True))
            if info.supported_programs:
                programs = ", ".join(info.supported_programs)
                platform_rows.append((tr("supported_programs"), programs, COLORS['accent_primary'], True))

            platforms_section = InfoSection(tr("section_platforms"), platform_rows)
            sections_layout.addWidget(platforms_section)

        # === Flags Section ===
        flags = []
        if info.can_contain_content:
            flags.append((tr("content"), tr("yes"), COLORS['success']))
        if info.can_contain_verse:
            flags.append((tr("can_contain_verse"), tr("yes"), COLORS['success']))
        if info.is_beta_version:
            flags.append((tr("beta"), tr("yes"), COLORS['warning']))
        if info.is_experimental_version:
            flags.append((tr("experimental"), tr("yes"), COLORS['warning']))
        if info.enabled_by_default:
            flags.append((tr("enabled_by_default"), tr("yes"), COLORS['success']))
        if info.installed:
            flags.append((tr("installed"), tr("yes"), COLORS['success']))
        if info.is_hidden:
            flags.append((tr("hidden"), tr("yes"), COLORS['warning']))
        if info.is_sealed:
            flags.append((tr("sealed"), tr("yes"), COLORS['warning']))
        if info.no_code:
            flags.append((tr("no_code"), tr("yes"), COLORS['text_secondary']))
        if info.explicitly_loaded:
            flags.append((tr("explicitly_loaded"), tr("yes"), COLORS['warning']))
        if info.is_plugin_extension:
            flags.append((tr("plugin_extension"), tr("yes"), COLORS['accent_primary']))
        if info.requires_build_platform:
            flags.append((tr("requires_build_platform"), tr("yes"), COLORS['warning']))

        if flags:
            flags_section = InfoSection(tr("section_flags"), flags)
            sections_layout.addWidget(flags_section)

        # === URLs Section ===
        urls = []
        if info.docs_url:
            urls.append((tr("docs_url"), info.docs_url, None, False, True))
        if info.marketplace_url:
            urls.append((tr("marketplace_url"), info.marketplace_url, None, False, True))
        if info.support_url:
            urls.append((tr("support_url"), info.support_url, None, False, True))
        if info.created_by_url:
            urls.append((tr("author_url"), info.created_by_url, None, False, True))

        if urls:
            urls_section = InfoSection(tr("section_links"), urls)
            sections_layout.addWidget(urls_section)

        sections_layout.addStretch()
        self._content_layout.insertWidget(0, self._content_widget)
    
    def set_items(self, items: List[Tuple[str, str]]) -> None:
        """
        Set simple items to display (legacy method).
        
        Args:
            items: List of (label, value) tuples
        """
        self.clear_items()
        
        if not items:
            self._empty_label.setVisible(True)
            return
        
        self._empty_label.setVisible(False)
        
        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        items_layout = QVBoxLayout(self._content_widget)
        items_layout.setContentsMargins(0, 0, 0, 0)
        items_layout.setSpacing(8)
        
        for label, value in items:
            row = InfoRow(label, value)
            items_layout.addWidget(row)
        
        items_layout.addStretch()
        self._content_layout.insertWidget(0, self._content_widget)
    
    def clear_items(self) -> None:
        """Clear all items and collapse card."""
        if self._content_widget:
            self._content_widget.setParent(None)
            self._content_widget.deleteLater()
            self._content_widget = None
        
        self._empty_label.setVisible(True)
        # Collapse card when cleared
        self._set_expanded(False)
    
    def _set_expanded(self, expanded: bool) -> None:
        """Set card expanded or collapsed state."""
        self._is_expanded = expanded
        if expanded:
            self.setMinimumHeight(self.EXPANDED_HEIGHT)
            self.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        else:
            self.setMinimumHeight(self.COMPACT_HEIGHT)
            self.setMaximumHeight(self.COMPACT_HEIGHT)
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    
    def set_title(self, title: str) -> None:
        """Set the card title."""
        self._title = title
        self._title_label.setText(title)
