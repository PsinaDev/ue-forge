"""
Renamer page for UE Forge.

Supports renaming both Unreal Engine plugins (.uplugin) and projects (.uproject).
Auto-detects mode from the dropped file extension.
Left panel: drop zone + name inputs + scope.
Right panel: live diff-style preview + execute.
Matches the JSX reference design exactly.
"""
import html as _html
import re
from pathlib import Path
from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QLineEdit,
    QCheckBox,
    QSplitter,
    QScrollArea,
    QProgressBar,
    QTextBrowser,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject, QSize

from ue_forge.shared.styles import COLORS, FONTS, RADIUS
from ue_forge.shared.icons import Icons
from ue_forge.shared.widgets import PathInput, ConsoleWidget
from pyside_frameless import DropZoneWidget
from ue_forge.shared.dialogs import MessageDialog
from ue_forge.shared.types import LogLevel, LogMessage
from ue_forge.shared.localization import tr
from ue_forge.plugin_builder.builder import PluginBuilder
from .core import (
    ChangeType,
    RenameChange,
    RenameScope,
    RenameResult,
    RenameStatus,
    PluginRenamer,
    ProjectRenamer,
)


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _PreviewWorker(QObject):
    finished = Signal(int, object)  # (generation, List[RenameChange])
    progress = Signal(int)

    def __init__(self, gen: int, is_project: bool, file_path: Path, old_name: str, new_name: str, scope: RenameScope):
        super().__init__()
        self._gen = gen
        self._is_project = is_project
        self._file_path = file_path
        self._old_name = old_name
        self._new_name = new_name
        self._scope = scope

    def run(self) -> None:
        pcb = lambda v: self.progress.emit(v)
        if self._is_project:
            r = ProjectRenamer(progress_callback=pcb)
            changes = r.preview(self._file_path, self._old_name, self._new_name, self._scope)
        else:
            r = PluginRenamer(progress_callback=pcb)
            changes = r.preview(self._file_path, self._old_name, self._new_name, self._scope)
        self.finished.emit(self._gen, changes)


class _ExecuteWorker(QObject):
    finished = Signal(object)
    log_message = Signal(object)

    def __init__(self, is_project: bool, file_path: Path, old_name: str, new_name: str, scope: RenameScope):
        super().__init__()
        self._is_project = is_project
        self._file_path = file_path
        self._old_name = old_name
        self._new_name = new_name
        self._scope = scope

    def run(self) -> None:
        cb = lambda msg: self.log_message.emit(msg)
        if self._is_project:
            result = ProjectRenamer(log_callback=cb).execute(self._file_path, self._old_name, self._new_name, self._scope)
        else:
            result = PluginRenamer(log_callback=cb).execute(self._file_path, self._old_name, self._new_name, self._scope)
        self.finished.emit(result)


# ---------------------------------------------------------------------------
# Preview widgets (matching JSX reference)
# ---------------------------------------------------------------------------

_BODY_BORDER_STYLE = f"border-top: 1px solid {COLORS['border_default']}"


def _esc(text: str) -> str:
    """Escape HTML entities in diff text."""
    return _html.escape(text, quote=False)


def _render_changes_html(changes: List[RenameChange]) -> str:
    """Render a list of changes as a single HTML string for QTextBrowser.

    One HTML block per change — vastly faster than 200+ QWidget instances.
    """
    mono = FONTS['family_mono']
    err = COLORS['error']
    ok = COLORS['success']
    dim = COLORS['text_dim']
    err_bg = "rgba(248,113,113,0.12)"
    ok_bg = "rgba(52,211,153,0.12)"

    parts: List[str] = []
    for c in changes:
        if c.is_file_op:
            parts.append(
                f'<div style="margin:3px 0;">'
                f'<div style="background:{err_bg};color:{err};padding:3px 8px;'
                f'border-radius:3px;font-family:{mono};font-size:11px;'
                f'white-space:nowrap;">{_esc(c.old_value)}</div>'
                f'<div style="background:{ok_bg};color:{ok};padding:3px 8px;'
                f'border-radius:3px;font-family:{mono};font-size:11px;'
                f'white-space:nowrap;">{_esc(c.new_value)}</div>'
                f'</div>'
            )
        else:
            parts.append(
                f'<div style="margin:3px 0;">'
                f'<div style="color:{dim};font-family:{mono};font-size:10px;'
                f'white-space:nowrap;">{_esc(c.file_path)}</div>'
                f'<div style="background:{err_bg};color:{err};padding:3px 8px;'
                f'border-radius:3px;font-family:{mono};font-size:11px;'
                f'white-space:nowrap;">- {_esc(c.old_value)}</div>'
                f'<div style="background:{ok_bg};color:{ok};padding:3px 8px;'
                f'border-radius:3px;font-family:{mono};font-size:11px;'
                f'white-space:nowrap;">+ {_esc(c.new_value)}</div>'
                f'</div>'
            )
    return "".join(parts)


class _PreviewCategory(QWidget):
    """Collapsible category with HTML-rendered diff body inside a capped scroll area."""

    CATEGORY_STYLE = {
        "File System": ("FOLDER_OPEN", COLORS['accent_primary']),
        "Plugin Root": ("FOLDER_OPEN", COLORS['accent_primary']),
        "Project Root": ("FOLDER_OPEN", COLORS['accent_primary']),
        ".uplugin Contents": ("FILE_CODE", COLORS['warning']),
        ".uproject Contents": ("FILE_CODE", COLORS['warning']),
        "Target Files": ("FILE_CODE", COLORS['warning']),
        "API Macros": ("HASH", COLORS['error']),
        "Module Macros": ("TERMINAL", COLORS['accent_primary']),
        "C# Source": ("WRENCH", COLORS['warning']),
        "Include Paths": ("BRACES", COLORS['text_muted']),
        "Comments": ("FILE_CODE", COLORS['text_dim']),
        "Config Files": ("FILE_CODE", COLORS['warning']),
    }

    def __init__(
        self,
        category: str,
        changes: List[RenameChange],
        *,
        expanded: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._changes = changes
        self._expanded = False
        self._body_built = False
        self.setStyleSheet("background: transparent; border: none;")

        icon_name, color = self.CATEGORY_STYLE.get(category, ("PUZZLE", COLORS['accent_primary']))
        if category.startswith("Module:"):
            icon_name = "PUZZLE"
            color = COLORS['accent_primary']

        self._build_ui(category, icon_name, color)
        if expanded:
            self._toggle()

    def _build_ui(self, category: str, icon_name: str, color: str) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        container = QFrame()
        container.setObjectName("previewCat")
        container.setStyleSheet(f"""
            QFrame#previewCat {{
                border: 1px solid {COLORS['border_default']};
                border-radius: 8px;
                background: transparent;
            }}
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Header button
        self._header = QPushButton()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(40)
        self._header.clicked.connect(self._toggle)
        self._header.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_secondary']};
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_tertiary']};
            }}
        """)

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(8)

        self._chevron = QLabel()
        self._chevron.setFixedSize(12, 12)
        self._chevron.setPixmap(Icons.get_pixmap("CHEVRON_RIGHT", 12, COLORS['text_dim']))
        hl.addWidget(self._chevron)

        cat_icon = QLabel()
        cat_icon.setPixmap(Icons.get_pixmap(icon_name, 14, color))
        cat_icon.setFixedSize(14, 14)
        hl.addWidget(cat_icon)

        title = QLabel(category)
        title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: {FONTS['size_xs']};"
            f" font-weight: 500; background: transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()

        badge = QLabel(str(len(self._changes)))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
            " background: transparent; border: none; padding: 0;"
        )
        hl.addWidget(badge)

        container_layout.addWidget(self._header)

        # Body container — no internal vertical scroll; outer _preview_scroll handles that.
        # QTextBrowser inside will auto-size to content height.
        self._body_frame = QWidget()
        self._body_frame.setVisible(False)
        self._body_frame.setStyleSheet(
            f"background: transparent; border: none; {_BODY_BORDER_STYLE};"
        )
        body_lay = QVBoxLayout(self._body_frame)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        container_layout.addWidget(self._body_frame)
        root_layout.addWidget(container)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._body_frame.setVisible(self._expanded)
        icon = "CHEVRON_DOWN" if self._expanded else "CHEVRON_RIGHT"
        self._chevron.setPixmap(Icons.get_pixmap(icon, 12, COLORS['text_dim']))

        if self._expanded and not self._body_built:
            self._body_built = True
            browser = QTextBrowser()
            browser.setOpenLinks(False)
            browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            browser.setLineWrapMode(QTextBrowser.LineWrapMode.NoWrap)
            browser.setStyleSheet(
                "QTextBrowser { background: transparent; border: none;"
                " padding: 8px 14px 12px 24px; }"
            )
            browser.setHtml(_render_changes_html(self._changes))
            # Size to content: full height, horizontal scroll for overflow
            doc_height = int(browser.document().size().height()) + 24
            browser.setFixedHeight(doc_height)
            self._body_frame.layout().addWidget(browser)


# ---------------------------------------------------------------------------
# Left config panel
# ---------------------------------------------------------------------------

class _ConfigPanel(DropZoneWidget):
    """Left panel: drop zone, name inputs, scope options."""

    config_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, valid_extensions=[".uplugin", ".uproject"], allow_directories=True)
        self._detected_name: str = ""
        self._is_project: bool = False
        self._engine_version: str = ""
        self._setup_ui()
        overlay = self.setup_drop_overlay()
        overlay.configure(
            valid_pixmap=Icons.get_pixmap("UPLOAD", 48, "rgba(34, 211, 238, 1)"),
            invalid_pixmap=Icons.get_pixmap("X_CIRCLE", 48, "rgba(248, 113, 113, 1)"),
            invalid_text=tr("invalid_drop_file"),
        )
        self.set_drop_callback(self._on_file_dropped)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        hdr_icon = QLabel()
        hdr_icon.setPixmap(Icons.get_pixmap("TYPE", 20, COLORS['accent_primary']))
        hdr_icon.setFixedSize(20, 20)
        hdr.addWidget(hdr_icon)
        hdr_title = QLabel(tr("renamer_title"))
        hdr_title.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: {FONTS['size_xl']}; font-weight: 600;")
        hdr.addWidget(hdr_title)
        hdr.addStretch()
        cl.addLayout(hdr)

        # Drop zone / plugin info
        self._file_input = PathInput(
            label=tr("select_uplugin_or_uproject"),
            placeholder=tr("path_to_plugin_file"),
            hint=tr("drag_drop_rename_hint"),
            icon_name="FILE_CODE",
            file_filter="Unreal Files (*.uplugin *.uproject)",
        )
        self._file_input.path_changed.connect(self._on_path_changed)
        cl.addWidget(self._file_input)

        # Name inputs card
        name_card = self._card()
        name_layout = QVBoxLayout(name_card)
        name_layout.setContentsMargins(16, 16, 16, 16)
        name_layout.setSpacing(12)

        cur_label = QLabel(tr("current_name"))
        cur_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: {FONTS['size_sm']}; font-weight: 500;")
        name_layout.addWidget(cur_label)

        self._current_name = QLineEdit()
        self._current_name.setReadOnly(True)
        self._current_name.setStyleSheet(f"background: {COLORS['bg_tertiary']}; color: {COLORS['text_muted']}; font-family: {FONTS['family_mono']};")
        name_layout.addWidget(self._current_name)

        # Arrow down
        arrow_row = QHBoxLayout()
        arrow_row.addStretch()
        arrow = QLabel()
        arrow.setPixmap(Icons.get_pixmap("ARROW_RIGHT", 16, COLORS['text_dim']))
        arrow.setFixedSize(16, 16)
        arrow_row.addWidget(arrow)
        arrow_row.addStretch()
        name_layout.addLayout(arrow_row)

        # New name header with icon
        new_hdr = QHBoxLayout()
        new_hdr.setSpacing(6)
        new_icon = QLabel()
        new_icon.setPixmap(Icons.get_pixmap("TYPE", 14, COLORS['accent_primary']))
        new_icon.setFixedSize(14, 14)
        new_hdr.addWidget(new_icon)
        new_label = QLabel(tr("new_name"))
        new_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: {FONTS['size_sm']}; font-weight: 500;")
        new_hdr.addWidget(new_label)
        new_hdr.addStretch()
        name_layout.addLayout(new_hdr)

        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText(tr("enter_new_name"))
        self._new_name.setStyleSheet(f"font-family: {FONTS['family_mono']};")
        self._new_name.textChanged.connect(self._emit_changed)
        name_layout.addWidget(self._new_name)

        # Validation
        self._validation = QLabel()
        self._validation.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['error']};
                font-size: {FONTS['size_xs']};
                background: {COLORS['error_bg']};
                border: none;
                border-radius: 6px;
                padding: 6px 10px;
            }}
        """)
        self._validation.setVisible(False)
        name_layout.addWidget(self._validation)

        cl.addWidget(name_card)

        # Scope card
        scope_card = self._card()
        scope_layout = QVBoxLayout(scope_card)
        scope_layout.setContentsMargins(16, 16, 16, 16)
        scope_layout.setSpacing(2)

        # Scope header
        scope_hdr = QHBoxLayout()
        scope_hdr.setSpacing(6)
        scope_icon = QLabel()
        scope_icon.setPixmap(Icons.get_pixmap("EYE", 14, COLORS['accent_primary']))
        scope_icon.setFixedSize(14, 14)
        scope_hdr.addWidget(scope_icon)
        scope_title = QLabel(tr("rename_scope"))
        scope_title.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: {FONTS['size_sm']}; font-weight: 500;")
        scope_hdr.addWidget(scope_title)
        scope_hdr.addStretch()
        scope_layout.addLayout(scope_hdr)
        scope_layout.addSpacing(8)

        # Scope items with descriptions
        self._scope_checks: Dict[str, QCheckBox] = {}
        scope_items = [
            ("rename_modules", "scope_modules", "scope_modules_desc"),
            ("rename_api_macros", "scope_api_macros", "scope_api_macros_desc"),
            ("rename_includes", "scope_includes", "scope_includes_desc"),
            ("rename_module_macros", "scope_module_macros", "scope_module_macros_desc"),
            ("rename_comments", "scope_comments", "scope_comments_desc"),
        ]
        for key, label_key, desc_key in scope_items:
            cb = QCheckBox(tr(label_key))
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_changed)
            scope_layout.addWidget(cb)

            desc = QLabel(tr(desc_key))
            desc.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']}; padding-left: 30px; padding-bottom: 6px; background: transparent; border: none;")
            desc.setWordWrap(True)
            scope_layout.addWidget(desc)

            self._scope_checks[key] = cb

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS['border_default']}; border: none; margin: 6px 0;")
        scope_layout.addWidget(sep)

        # Backup
        self._backup_check = QCheckBox(tr("scope_backup"))
        self._backup_check.setChecked(True)
        self._backup_check.stateChanged.connect(self._emit_changed)
        scope_layout.addWidget(self._backup_check)

        backup_desc = QLabel(tr("scope_backup_desc"))
        backup_desc.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']}; padding-left: 30px; background: transparent; border: none;")
        scope_layout.addWidget(backup_desc)

        cl.addWidget(scope_card)
        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("renamerCard")
        f.setStyleSheet(f"""
            QFrame#renamerCard {{
                background-color: rgba(24, 24, 27, 0.3);
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
        """)
        return f

    # Accessors

    @property
    def is_project_mode(self) -> bool:
        return self._is_project

    @property
    def file_path(self) -> str:
        return self._file_input.path()

    @property
    def old_name(self) -> str:
        return self._detected_name

    @property
    def new_name(self) -> str:
        return self._new_name.text().strip()

    @property
    def is_valid(self) -> bool:
        n = self.new_name
        if not n or n == self.old_name:
            return False
        return bool(re.match(r'^[A-Za-z][A-Za-z0-9]*$', n))

    def get_scope(self) -> RenameScope:
        macros = self._scope_checks["rename_module_macros"].isChecked()
        return RenameScope(
            rename_modules=self._scope_checks["rename_modules"].isChecked(),
            rename_api_macros=self._scope_checks["rename_api_macros"].isChecked(),
            rename_includes=self._scope_checks["rename_includes"].isChecked(),
            rename_build_cs=macros,
            rename_module_macros=macros,
            rename_comments=self._scope_checks["rename_comments"].isChecked(),
            create_backup=self._backup_check.isChecked(),
        )

    # Slots

    def _on_file_dropped(self, path: str) -> None:
        self._file_input.set_path(path)

    def _on_path_changed(self, path: str) -> None:
        if not path:
            self._detected_name = ""
            self._is_project = False
            self._current_name.setText("")
        else:
            p = Path(path)
            self._detected_name = p.stem
            self._is_project = p.suffix == ".uproject"
            self._current_name.setText(self._detected_name)
            # Try to get engine version for plugin info
            if p.suffix == ".uplugin":
                info = PluginBuilder.extract_plugin_info(p)
                self._engine_version = info.engine_version if info else ""
        self._emit_changed()

    def _emit_changed(self) -> None:
        n = self.new_name
        if n and not self.is_valid:
            self._validation.setText(
                tr("name_validation_same") if n == self.old_name else tr("name_validation_format")
            )
            self._validation.setVisible(True)
        else:
            self._validation.setVisible(False)
        self.config_changed.emit()


# ---------------------------------------------------------------------------
# RenamerPage
# ---------------------------------------------------------------------------

class RenamerPage(QWidget):
    """Renamer page matching JSX reference design."""

    PAGE_ID = "renamer"
    PAGE_ICON = "TYPE"

    status_changed = Signal(str, str)

    LEFT_PANEL_WIDTH = 440

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._preview_changes: List[RenameChange] = []
        self._exec_thread: Optional[QThread] = None
        self._exec_worker: Optional[_ExecuteWorker] = None

        # Generation counter: each new preview request increments this.
        # Stale results (from old threads still running) are discarded.
        self._preview_gen: int = 0
        # Keep refs to prevent GC while threads run. Cleaned up on thread finish.
        self._active_threads: List = []

        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(500)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self._setup_ui()
        self._config.config_changed.connect(self._on_config_changed)

    @staticmethod
    def page_title() -> str:
        return tr("renamer")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {COLORS['border_default']}; }}")

        self._config = _ConfigPanel()
        self._config.setFixedWidth(self.LEFT_PANEL_WIDTH)
        splitter.addWidget(self._config)

        right = self._build_right_panel()
        right.setMinimumWidth(400)
        splitter.addWidget(right)

        splitter.setSizes([self.LEFT_PANEL_WIDTH, 720])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.handle(1).setEnabled(False)
        splitter.handle(1).setCursor(Qt.CursorShape.ArrowCursor)

        layout.addWidget(splitter, 1)

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Preview header bar
        header = QFrame()
        header.setObjectName("previewHeader")
        header.setFixedHeight(40)
        header.setStyleSheet(f"""
            QFrame#previewHeader {{
                background: {COLORS['bg_secondary']};
                border: none;
                border-bottom: 1px solid {COLORS['border_default']};
            }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(8)

        pi = QLabel()
        pi.setPixmap(Icons.get_pixmap("EYE", 16, COLORS['accent_primary']))
        pi.setFixedSize(16, 16)
        hl.addWidget(pi)

        pt = QLabel(tr("preview"))
        pt.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: {FONTS['size_sm']}; font-weight: 600;")
        hl.addWidget(pt)

        self._changes_badge = QLabel()
        self._changes_badge.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
            " background: transparent; border: none; padding: 0;"
        )
        self._changes_badge.setVisible(False)
        hl.addWidget(self._changes_badge)
        hl.addStretch()

        layout.addWidget(header)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # Scrollable preview area
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._preview_container = QWidget()
        self._preview_container.setStyleSheet("background: transparent; border: none;")
        self._preview_layout = QVBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(20, 20, 20, 20)
        self._preview_layout.setSpacing(10)
        self._preview_layout.addStretch()

        self._preview_scroll.setWidget(self._preview_container)

        # Empty state
        self._empty_label = QLabel(tr("preview_empty"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: {FONTS['size_sm']};")

        # Console (shown during execution)
        self._console = ConsoleWidget()
        self._console.setVisible(False)

        layout.addWidget(self._empty_label, 1)
        layout.addWidget(self._preview_scroll, 1)
        layout.addWidget(self._console, 1)
        self._preview_scroll.setVisible(False)

        # Bottom control bar
        controls = QFrame()
        controls.setObjectName("renamerControls")
        controls.setFixedHeight(64)
        controls.setStyleSheet(f"""
            QFrame#renamerControls {{
                background: rgba(24, 24, 27, 0.5);
                border: none;
                border-top: 1px solid {COLORS['border_default']};
            }}
        """)
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(16, 0, 16, 0)
        cl.setSpacing(12)
        cl.addStretch()

        self._rename_btn = QPushButton(f"  {tr('rename_plugin')}")
        self._rename_btn.setIcon(Icons.get_icon("PLAY", 16, "#ffffff"))
        self._rename_btn.setProperty("class", "primary")
        self._rename_btn.setFixedWidth(180)
        self._rename_btn.setFixedHeight(40)
        self._rename_btn.setCursor(Qt.PointingHandCursor)
        self._rename_btn.setEnabled(False)
        self._rename_btn.clicked.connect(self._execute_rename)
        cl.addWidget(self._rename_btn)

        layout.addWidget(controls)
        return panel

    # ------------------------------------------------------------------
    # Config change handler
    # ------------------------------------------------------------------

    def _on_config_changed(self) -> None:
        valid = self._config.is_valid and bool(self._config.file_path)
        self._rename_btn.setEnabled(valid)

        self._rename_btn.setText(
            f"  {tr('rename_project')}" if self._config.is_project_mode else f"  {tr('rename_plugin')}"
        )

        if valid:
            # Debounce: start/restart timer for preview refresh
            self._preview_timer.start()
        else:
            # Stop pending preview, show empty state (cheap — just hide/show)
            self._preview_timer.stop()
            self._preview_gen += 1  # invalidate any in-flight preview
            if self._preview_changes:
                self._preview_changes = []
                self._update_preview()
            else:
                # Already showing empty state — just update the label text
                has_file = bool(self._config.file_path)
                self._empty_label.setText(tr("preview_enter_name") if has_file else tr("preview_empty"))
                self._empty_label.setVisible(True)
                self._preview_scroll.setVisible(False)
                self._changes_badge.setVisible(False)
                self._progress_bar.setVisible(False)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _refresh_preview(self) -> None:
        if not self._config.is_valid or not self._config.file_path:
            self._preview_changes = []
            self._update_preview()
            return

        # Increment generation — any in-flight worker with older gen will be ignored
        self._preview_gen += 1
        gen = self._preview_gen

        # Show progress
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        thread = QThread()
        worker = _PreviewWorker(
            gen,
            self._config.is_project_mode,
            Path(self._config.file_path),
            self._config.old_name,
            self._config.new_name,
            self._config.get_scope(),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_preview_done, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        worker.progress.connect(
            self._on_preview_progress, Qt.ConnectionType.QueuedConnection
        )

        # prevent GC: store refs, clean up after thread finishes
        pair = (thread, worker)
        self._active_threads.append(pair)
        thread.finished.connect(lambda p=pair: self._active_threads.remove(p) if p in self._active_threads else None)

        thread.start()

    @Slot(int, object)
    def _on_preview_done(self, gen: int, changes) -> None:
        # Ignore stale results from old preview runs
        if gen != self._preview_gen:
            return
        self._preview_changes = changes if changes else []
        self._progress_bar.setVisible(False)
        self._update_preview()

    @Slot(int)
    def _on_preview_progress(self, value: int) -> None:
        self._progress_bar.setValue(value)

    @Slot(object)
    def _on_log_message(self, msg) -> None:
        self._console.append_log(msg)

    def _update_preview(self) -> None:
        """Rebuild preview. Categories are lazy — diff lines created only on expand."""
        # Fast cleanup: replace entire container widget
        old = self._preview_scroll.takeWidget()
        if old:
            old.deleteLater()

        self._preview_container = QWidget()
        self._preview_container.setStyleSheet("background: transparent; border: none;")
        self._preview_layout = QVBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(20, 20, 20, 20)
        self._preview_layout.setSpacing(10)
        self._preview_scroll.setWidget(self._preview_container)

        changes = self._preview_changes
        has_file = bool(self._config.file_path)
        is_valid = self._config.is_valid

        if not has_file:
            self._empty_label.setText(tr("preview_empty"))
            self._empty_label.setVisible(True)
            self._preview_scroll.setVisible(False)
            self._console.setVisible(False)
            self._changes_badge.setVisible(False)
            return

        if not is_valid or not changes:
            self._empty_label.setText(tr("preview_enter_name") if has_file else tr("preview_empty"))
            self._empty_label.setVisible(True)
            self._preview_scroll.setVisible(False)
            self._console.setVisible(False)
            self._changes_badge.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._preview_scroll.setVisible(True)
        self._console.setVisible(False)

        # Group by category (preserving insertion order)
        categories: Dict[str, List[RenameChange]] = {}
        for c in changes:
            categories.setdefault(c.category, []).append(c)

        self._changes_badge.setText(tr("changes_summary", count=len(changes), cats=len(categories)))
        self._changes_badge.setVisible(True)

        # Create category headers (cheap). Diff lines are lazy (created on expand).
        for i, (cat_name, cat_changes) in enumerate(categories.items()):
            w = _PreviewCategory(cat_name, cat_changes, expanded=(i < 3))
            self._preview_layout.addWidget(w)

        self._preview_layout.addStretch()

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _execute_rename(self) -> None:
        if not self._config.is_valid:
            return

        old = self._config.old_name
        new = self._config.new_name

        result = MessageDialog.question(
            self,
            tr("rename_project") if self._config.is_project_mode else tr("rename_plugin"),
            tr("rename_started", old=old, new=new) + f"\n\n{len(self._preview_changes)} changes will be applied.",
            [tr("no"), tr("yes")],
        )
        if result != tr("yes"):
            return

        self._empty_label.setVisible(False)
        self._preview_scroll.setVisible(False)
        self._console.setVisible(True)
        self._console.clear()
        self._rename_btn.setEnabled(False)
        self.status_changed.emit("running", tr("rename_in_progress"))

        self._exec_thread = QThread()
        self._exec_worker = _ExecuteWorker(
            self._config.is_project_mode,
            Path(self._config.file_path),
            old, new, self._config.get_scope(),
        )
        self._exec_worker.moveToThread(self._exec_thread)
        self._exec_thread.started.connect(self._exec_worker.run)
        self._exec_worker.finished.connect(self._on_exec_done, Qt.ConnectionType.QueuedConnection)
        self._exec_worker.finished.connect(self._exec_thread.quit)
        self._exec_worker.log_message.connect(self._on_log_message, Qt.ConnectionType.QueuedConnection)
        self._exec_thread.start()

    @Slot(object)
    def _on_exec_done(self, result: RenameResult) -> None:
        self._rename_btn.setEnabled(True)
        if result.status == RenameStatus.SUCCESS and not result.errors:
            self.status_changed.emit("success", tr("success"))
            MessageDialog.information(self, tr("rename_complete"),
                tr("rename_successful", count=result.changes_applied, time=result.duration_seconds))
        else:
            self.status_changed.emit("failed", tr("failed"))
            summary = "\n".join(result.errors[:5]) if result.errors else result.message
            MessageDialog.error(self, tr("rename_failed"), tr("rename_failed_msg", error=summary))

    # Host interface

    def get_settings_tabs(self):
        """Return settings tabs contributed by this page."""
        return []

    def show_settings(self) -> None:
        """Show settings dialog (called by host/standalone shell)."""
        from ue_forge.shared.dialogs import SettingsDialog
        SettingsDialog(self, extra_tabs=self.get_settings_tabs()).exec()

    def can_close(self) -> bool:
        if self._exec_thread and self._exec_thread.isRunning():
            result = MessageDialog.question(
                self,
                tr("rename_in_progress"),
                tr("rename_cancel_and_exit"),
                [tr("no"), tr("yes")],
            )
            return result == tr("yes")
        return True

    def cleanup(self) -> None:
        # Invalidate any in-flight preview
        self._preview_gen += 1
        # Only wait for execute thread (if running)
        try:
            if self._exec_thread is not None and self._exec_thread.isRunning():
                self._exec_thread.quit()
                self._exec_thread.wait(3000)
        except RuntimeError:
            pass