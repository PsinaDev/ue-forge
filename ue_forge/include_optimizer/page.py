"""
Include Optimizer page for UE Forge.

Scans UE project Source/ directories and applies include optimizations:
    - Missing ``UE_INLINE_GENERATED_CPP_BY_NAME``
    - ``CoreMinimal.h`` → specific headers
    - Duplicate ``#include`` removal

Left panel: drop zone + optimization scope.
Right panel: live preview + execute.
"""
from __future__ import annotations

import html as _html
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QCheckBox,
    QSplitter,
    QScrollArea,
    QProgressBar,
    QTextBrowser,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject

from ue_forge.shared.styles import COLORS, FONTS, RADIUS
from ue_forge.shared.icons import Icons
from ue_forge.shared.widgets import PathInput, ConsoleWidget
from ue_forge.shared.dialogs import MessageDialog
from ue_forge.shared.types import LogLevel, LogMessage
from ue_forge.shared.localization import tr
from pyside_frameless import DropZoneWidget

from .core import (
    ChangeType,
    IncludeChange,
    IncludeAnalyzer,
    OptimizeScope,
    OptimizeResult,
    OptimizeStatus,
    PluginInfo,
    find_plugins,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _PreviewWorker(QObject):
    """Background worker for scanning source files."""

    finished = Signal(int, object)  # (generation, list[IncludeChange])
    progress = Signal(int)

    def __init__(
        self,
        gen: int,
        path: Path,
        scope: OptimizeScope,
    ) -> None:
        super().__init__()
        self._gen = gen
        self._path = path
        self._scope = scope

    def run(self) -> None:
        pcb = lambda v: self.progress.emit(v)
        analyzer = IncludeAnalyzer(progress_callback=pcb)
        changes = analyzer.preview(self._path, self._scope)
        self.finished.emit(self._gen, changes)


class _ExecuteWorker(QObject):
    """Background worker for applying optimizations."""

    finished = Signal(object)  # OptimizeResult
    log_message = Signal(object)  # LogMessage

    def __init__(self, path: Path, scope: OptimizeScope) -> None:
        super().__init__()
        self._path = path
        self._scope = scope

    def run(self) -> None:
        cb = lambda msg: self.log_message.emit(msg)
        result = IncludeAnalyzer(log_callback=cb).execute(self._path, self._scope)
        self.finished.emit(result)


# ---------------------------------------------------------------------------
# Preview rendering
# ---------------------------------------------------------------------------

_BODY_BORDER_STYLE = f"border-top: 1px solid {COLORS['border_default']}"


def _esc(text: str) -> str:
    return _html.escape(text, quote=False)


def _render_changes_html(changes: list[IncludeChange]) -> str:
    """Render changes as HTML for QTextBrowser."""
    mono = FONTS['family_mono']
    err = COLORS['error']
    ok = COLORS['success']
    dim = COLORS['text_dim']
    err_bg = "rgba(248,113,113,0.12)"
    ok_bg = "rgba(52,211,153,0.12)"

    parts: list[str] = []
    for c in changes:
        parts.append(
            f'<div style="margin:3px 0;">'
            f'<div style="color:{dim};font-family:{mono};font-size:10px;'
            f'white-space:nowrap;">{_esc(c.file_path)}:{c.line_number}</div>'
            f'<div style="background:{err_bg};color:{err};padding:3px 8px;'
            f'border-radius:3px;font-family:{mono};font-size:11px;'
            f'white-space:nowrap;">- {_esc(c.old_value)}</div>'
            f'<div style="background:{ok_bg};color:{ok};padding:3px 8px;'
            f'border-radius:3px;font-family:{mono};font-size:11px;'
            f'white-space:pre-wrap;">+ {_esc(c.new_value)}</div>'
            f'</div>'
        )
    return "".join(parts)


class _PreviewCategory(QWidget):
    """Collapsible category with lazy-built HTML diff body."""

    CATEGORY_STYLE: dict[str, tuple[str, str]] = {
        "UE_INLINE_GENERATED_CPP_BY_NAME": ("ZAP", COLORS['success']),
        "CoreMinimal Replacement": ("HASH", COLORS['warning']),
        "Duplicate Includes": ("TRASH_2", COLORS['error']),
        "Preprocessor Block Fix": ("ALERT_TRIANGLE", COLORS['warning']),
    }

    def __init__(
        self,
        category: str,
        changes: list[IncludeChange],
        *,
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._changes = changes
        self._expanded = False
        self._body_built = False
        self.setStyleSheet("background: transparent; border: none;")

        icon_name, color = self.CATEGORY_STYLE.get(
            category, ("PUZZLE", COLORS['accent_primary']),
        )
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
        self._chevron.setPixmap(
            Icons.get_pixmap("CHEVRON_RIGHT", 12, COLORS['text_dim']),
        )
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

        file_count = len({c.file_path for c in self._changes})
        badge = QLabel(f"{len(self._changes)} in {file_count} files")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
            " background: transparent; border: none; padding: 0;"
        )
        hl.addWidget(badge)

        container_layout.addWidget(self._header)

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
        self._chevron.setPixmap(
            Icons.get_pixmap(icon, 12, COLORS['text_dim']),
        )

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
            doc_height = int(browser.document().size().height()) + 24
            browser.setFixedHeight(doc_height)
            self._body_frame.layout().addWidget(browser)


class _SourceGroup(QWidget):
    """Collapsible group for a source (project or plugin) in the preview."""

    def __init__(
        self,
        label: str,
        changes: list[IncludeChange],
        *,
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._changes = changes
        self._expanded = False
        self._body_built = False
        self.setStyleSheet("background: transparent; border: none;")
        self._build_ui(label)
        if expanded:
            self._toggle()

    def _build_ui(self, label: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        container = QFrame()
        container.setObjectName("sourceGroup")
        container.setStyleSheet(f"""
            QFrame#sourceGroup {{
                border: 1px solid {COLORS['border_default']};
                border-radius: 10px;
                background: transparent;
            }}
        """)
        clayout = QVBoxLayout(container)
        clayout.setContentsMargins(0, 0, 0, 0)
        clayout.setSpacing(0)

        # Header
        self._header = QPushButton()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(44)
        self._header.clicked.connect(self._toggle)
        self._header.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_secondary']};
                border: none;
                border-radius: 10px;
                padding: 0 16px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {COLORS['bg_tertiary']};
            }}
        """)

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(8)

        self._chevron = QLabel()
        self._chevron.setFixedSize(14, 14)
        self._chevron.setPixmap(
            Icons.get_pixmap("CHEVRON_RIGHT", 14, COLORS['text_dim']),
        )
        hl.addWidget(self._chevron)

        is_plugin = label != ""
        icon_name = "PUZZLE" if is_plugin else "FOLDER_OPEN"
        icon_color = COLORS['accent_primary']
        display_label = label if is_plugin else tr("opt_source_project")

        src_icon = QLabel()
        src_icon.setPixmap(Icons.get_pixmap(icon_name, 16, icon_color))
        src_icon.setFixedSize(16, 16)
        hl.addWidget(src_icon)

        title = QLabel(display_label)
        title.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: {FONTS['size_sm']};"
            f" font-weight: 600; background: transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()

        file_count = len({c.file_path for c in self._changes})
        badge = QLabel(
            tr("opt_changes_summary",
               count=len(self._changes), files=file_count),
        )
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
            " background: transparent; border: none; padding: 0;"
        )
        hl.addWidget(badge)

        clayout.addWidget(self._header)

        self._body = QWidget()
        self._body.setVisible(False)
        self._body.setStyleSheet(
            f"background: transparent; border: none;"
            f" {_BODY_BORDER_STYLE};"
        )
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(12, 8, 12, 12)
        self._body_layout.setSpacing(8)

        clayout.addWidget(self._body)
        root.addWidget(container)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        icon = "CHEVRON_DOWN" if self._expanded else "CHEVRON_RIGHT"
        self._chevron.setPixmap(
            Icons.get_pixmap(icon, 14, COLORS['text_dim']),
        )

        if self._expanded and not self._body_built:
            self._body_built = True
            # Group changes by category
            cats: dict[str, list[IncludeChange]] = {}
            for c in self._changes:
                cats.setdefault(c.category, []).append(c)
            for i, (cat_name, cat_changes) in enumerate(cats.items()):
                w = _PreviewCategory(
                    cat_name, cat_changes, expanded=(i < 3),
                )
                self._body_layout.addWidget(w)


# ---------------------------------------------------------------------------
# Left config panel
# ---------------------------------------------------------------------------

class _ConfigPanel(DropZoneWidget):
    """Left panel: drop zone + optimization scope options."""

    config_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            valid_extensions=['.uproject', '.uplugin'],
            allow_directories=True,
        )
        self._setup_ui()
        overlay = self.setup_drop_overlay()
        overlay.configure(
            valid_pixmap=Icons.get_pixmap("UPLOAD", 48, "rgba(34, 211, 238, 1)"),
            invalid_pixmap=Icons.get_pixmap("X_CIRCLE", 48, "rgba(248, 113, 113, 1)"),
            invalid_text=tr("opt_invalid_drop"),
        )
        self.set_drop_callback(self._on_file_dropped)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        hdr_icon = QLabel()
        hdr_icon.setPixmap(
            Icons.get_pixmap("ZAP", 20, COLORS['accent_primary']),
        )
        hdr_icon.setFixedSize(20, 20)
        hdr.addWidget(hdr_icon)
        hdr_title = QLabel(tr("opt_title"))
        hdr_title.setStyleSheet(
            f"color: {COLORS['text_primary']};"
            f" font-size: {FONTS['size_xl']}; font-weight: 600;"
        )
        hdr.addWidget(hdr_title)
        hdr.addStretch()
        cl.addLayout(hdr)

        # Description
        desc = QLabel(tr("opt_description"))
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {COLORS['text_muted']};"
            f" font-size: {FONTS['size_sm']};"
        )
        cl.addWidget(desc)

        # Path input
        self._file_input = PathInput(
            label=tr("opt_select_project"),
            placeholder=tr("opt_path_placeholder"),
            hint=tr("opt_drag_drop_hint"),
            icon_name="FOLDER_OPEN",
            file_filter="UE Project/Plugin (*.uproject *.uplugin)",
        )
        self._file_input.path_changed.connect(self._on_path_changed)
        cl.addWidget(self._file_input)

        # Scope card
        scope_card = self._card()
        scope_layout = QVBoxLayout(scope_card)
        scope_layout.setContentsMargins(16, 16, 16, 16)
        scope_layout.setSpacing(2)

        scope_hdr = QHBoxLayout()
        scope_hdr.setSpacing(6)
        scope_icon = QLabel()
        scope_icon.setPixmap(
            Icons.get_pixmap("SETTINGS", 14, COLORS['accent_primary']),
        )
        scope_icon.setFixedSize(14, 14)
        scope_hdr.addWidget(scope_icon)
        scope_title = QLabel(tr("opt_scope"))
        scope_title.setStyleSheet(
            f"color: {COLORS['text_secondary']};"
            f" font-size: {FONTS['size_sm']}; font-weight: 500;"
        )
        scope_hdr.addWidget(scope_title)
        scope_hdr.addStretch()
        scope_layout.addLayout(scope_hdr)
        scope_layout.addSpacing(8)

        # Scope items
        self._scope_checks: dict[str, QCheckBox] = {}
        scope_items = [
            ("add_inline_generated", "opt_scope_inline", "opt_scope_inline_desc"),
            ("replace_coreminimal", "opt_scope_coreminimal", "opt_scope_coreminimal_desc"),
            ("remove_duplicates", "opt_scope_duplicates", "opt_scope_duplicates_desc"),
            ("fix_preprocessor_includes", "opt_scope_ppfix", "opt_scope_ppfix_desc"),
        ]
        for key, label_key, desc_key in scope_items:
            cb = QCheckBox(tr(label_key))
            cb.setChecked(True)
            cb.stateChanged.connect(self._emit_changed)
            scope_layout.addWidget(cb)

            desc_label = QLabel(tr(desc_key))
            desc_label.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
                " padding-left: 30px; padding-bottom: 6px;"
                " background: transparent; border: none;"
            )
            desc_label.setWordWrap(True)
            scope_layout.addWidget(desc_label)

            self._scope_checks[key] = cb

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(
            f"background: {COLORS['border_default']};"
            " border: none; margin: 6px 0;"
        )
        scope_layout.addWidget(sep)

        # Backup
        self._backup_check = QCheckBox(tr("scope_backup"))
        self._backup_check.setChecked(True)
        self._backup_check.stateChanged.connect(self._emit_changed)
        scope_layout.addWidget(self._backup_check)

        backup_desc = QLabel(tr("opt_scope_backup_desc"))
        backup_desc.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
            " padding-left: 30px; background: transparent; border: none;"
        )
        scope_layout.addWidget(backup_desc)

        cl.addWidget(scope_card)

        # Plugins card (visible only for .uproject)
        self._plugins_card = self._card()
        self._plugins_card.setVisible(False)
        plugins_layout = QVBoxLayout(self._plugins_card)
        plugins_layout.setContentsMargins(16, 16, 16, 16)
        plugins_layout.setSpacing(2)

        plugins_hdr = QHBoxLayout()
        plugins_hdr.setSpacing(6)
        pl_icon = QLabel()
        pl_icon.setPixmap(
            Icons.get_pixmap("PUZZLE", 14, COLORS['accent_primary']),
        )
        pl_icon.setFixedSize(14, 14)
        plugins_hdr.addWidget(pl_icon)
        pl_title = QLabel(tr("opt_plugins"))
        pl_title.setStyleSheet(
            f"color: {COLORS['text_secondary']};"
            f" font-size: {FONTS['size_sm']}; font-weight: 500;"
        )
        plugins_hdr.addWidget(pl_title)
        plugins_hdr.addStretch()
        plugins_layout.addLayout(plugins_hdr)
        plugins_layout.addSpacing(4)

        self._include_plugins_cb = QCheckBox(tr("opt_include_plugins"))
        self._include_plugins_cb.setChecked(False)
        self._include_plugins_cb.stateChanged.connect(self._on_include_plugins_changed)
        plugins_layout.addWidget(self._include_plugins_cb)

        inc_desc = QLabel(tr("opt_include_plugins_desc"))
        inc_desc.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
            " padding-left: 30px; padding-bottom: 4px;"
            " background: transparent; border: none;"
        )
        inc_desc.setWordWrap(True)
        plugins_layout.addWidget(inc_desc)

        self._plugins_list_widget = QWidget()
        self._plugins_list_widget.setStyleSheet(
            "background: transparent; border: none;"
        )
        self._plugins_list_layout = QVBoxLayout(self._plugins_list_widget)
        self._plugins_list_layout.setContentsMargins(16, 4, 0, 0)
        self._plugins_list_layout.setSpacing(1)
        self._plugins_list_widget.setVisible(False)
        plugins_layout.addWidget(self._plugins_list_widget)

        self._plugin_checks: dict[str, QCheckBox] = {}
        self._discovered_plugins: list[PluginInfo] = []

        cl.addWidget(self._plugins_card)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("optimizerCard")
        f.setStyleSheet(f"""
            QFrame#optimizerCard {{
                background-color: rgba(24, 24, 27, 0.3);
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
        """)
        return f

    # Accessors

    @property
    def file_path(self) -> str:
        return self._file_input.path()

    @property
    def has_valid_path(self) -> bool:
        p = self._file_input.path()
        if not p:
            return False
        path = Path(p)
        if path.is_file() and path.suffix in ('.uproject', '.uplugin'):
            return (path.parent / 'Source').is_dir()
        if path.is_dir():
            return (path / 'Source').is_dir() or path.name == 'Source'
        return False

    def get_scope(self) -> OptimizeScope:
        excluded = set()
        for name, cb in self._plugin_checks.items():
            if not cb.isChecked():
                excluded.add(name)
        return OptimizeScope(
            add_inline_generated=self._scope_checks['add_inline_generated'].isChecked(),
            replace_coreminimal=self._scope_checks['replace_coreminimal'].isChecked(),
            remove_duplicates=self._scope_checks['remove_duplicates'].isChecked(),
            fix_preprocessor_includes=self._scope_checks['fix_preprocessor_includes'].isChecked(),
            create_backup=self._backup_check.isChecked(),
            include_plugins=self._include_plugins_cb.isChecked(),
            excluded_plugins=excluded,
        )

    @property
    def discovered_plugins(self) -> list[PluginInfo]:
        return self._discovered_plugins

    # Handlers

    def _on_file_dropped(self, file_path: str) -> None:
        self._file_input.set_path(file_path)

    def _on_path_changed(self, _text: str) -> None:
        self._refresh_plugins()
        self._emit_changed()

    def _on_include_plugins_changed(self) -> None:
        self._plugins_list_widget.setVisible(
            self._include_plugins_cb.isChecked()
            and bool(self._plugin_checks),
        )
        self._emit_changed()

    def _refresh_plugins(self) -> None:
        """Discover plugins for the current path and rebuild the list."""
        # Clear old checkboxes
        while self._plugins_list_layout.count():
            item = self._plugins_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._plugin_checks.clear()
        self._discovered_plugins.clear()

        p = self._file_input.path()
        path = Path(p) if p else None
        is_uproject = (
            path is not None
            and path.is_file()
            and path.suffix == '.uproject'
        )

        self._plugins_card.setVisible(is_uproject)
        if not is_uproject:
            self._include_plugins_cb.setChecked(False)
            return

        plugins = find_plugins(path)
        self._discovered_plugins = plugins
        if not plugins:
            self._plugins_card.setVisible(False)
            return

        # Group by category
        cats: dict[str, list[PluginInfo]] = {}
        for pi in plugins:
            if pi.source_dir is None:
                continue
            cats.setdefault(pi.category, []).append(pi)

        for cat_name in sorted(cats):
            cat_label = QLabel(cat_name)
            cat_label.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
                " font-weight: 600; padding-top: 6px; padding-bottom: 2px;"
                " background: transparent; border: none;"
            )
            self._plugins_list_layout.addWidget(cat_label)

            for pi in sorted(cats[cat_name], key=lambda x: x.name):
                cb = QCheckBox(pi.name)
                cb.setChecked(True)
                cb.setStyleSheet(
                    f"color: {COLORS['text_secondary']};"
                    f" font-size: {FONTS['size_xs']};"
                    " background: transparent; border: none;"
                    " padding-left: 6px;"
                )
                cb.stateChanged.connect(self._emit_changed)
                self._plugins_list_layout.addWidget(cb)
                self._plugin_checks[pi.name] = cb

        self._plugins_list_widget.setVisible(
            self._include_plugins_cb.isChecked()
            and bool(self._plugin_checks),
        )

    def _emit_changed(self) -> None:
        self.config_changed.emit()


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

class IncludeOptimizerPage(QWidget):
    """Include Optimizer page matching project design language."""

    PAGE_ID = "include_optimizer"
    PAGE_ICON = "ZAP"

    status_changed = Signal(str, str)

    LEFT_PANEL_WIDTH = 440

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._preview_changes: list[IncludeChange] = []
        self._exec_thread: QThread | None = None
        self._exec_worker: _ExecuteWorker | None = None

        self._preview_gen: int = 0
        self._active_threads: list[tuple[QThread, _PreviewWorker]] = []

        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(500)
        self._preview_timer.timeout.connect(self._refresh_preview)

        self._setup_ui()
        self._config.config_changed.connect(self._on_config_changed)

    @staticmethod
    def page_title() -> str:
        return tr("include_optimizer")

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background-color:"
            f" {COLORS['border_default']}; }}"
        )

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
        header.setObjectName("optPreviewHeader")
        header.setFixedHeight(40)
        header.setStyleSheet(f"""
            QFrame#optPreviewHeader {{
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
        pt.setStyleSheet(
            f"color: {COLORS['text_primary']};"
            f" font-size: {FONTS['size_sm']}; font-weight: 600;"
        )
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
        self._preview_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self._preview_container = QWidget()
        self._preview_container.setStyleSheet(
            "background: transparent; border: none;"
        )
        self._preview_layout = QVBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(20, 20, 20, 20)
        self._preview_layout.setSpacing(10)
        self._preview_layout.addStretch()

        self._preview_scroll.setWidget(self._preview_container)

        # Empty state
        self._empty_label = QLabel(tr("opt_preview_empty"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {COLORS['text_dim']};"
            f" font-size: {FONTS['size_sm']};"
        )

        # Console (during execution)
        self._console = ConsoleWidget()
        self._console.setVisible(False)

        layout.addWidget(self._empty_label, 1)
        layout.addWidget(self._preview_scroll, 1)
        layout.addWidget(self._console, 1)
        self._preview_scroll.setVisible(False)

        # Bottom control bar
        controls = QFrame()
        controls.setObjectName("optControls")
        controls.setFixedHeight(64)
        controls.setStyleSheet(f"""
            QFrame#optControls {{
                background: rgba(24, 24, 27, 0.5);
                border: none;
                border-top: 1px solid {COLORS['border_default']};
            }}
        """)
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(16, 0, 16, 0)
        cl.setSpacing(12)
        cl.addStretch()

        self._optimize_btn = QPushButton(f"  {tr('opt_execute')}")
        self._optimize_btn.setIcon(Icons.get_icon("PLAY", 16, "#ffffff"))
        self._optimize_btn.setProperty("class", "primary")
        self._optimize_btn.setFixedWidth(180)
        self._optimize_btn.setFixedHeight(40)
        self._optimize_btn.setCursor(Qt.PointingHandCursor)
        self._optimize_btn.setEnabled(False)
        self._optimize_btn.clicked.connect(self._execute_optimize)
        cl.addWidget(self._optimize_btn)

        layout.addWidget(controls)
        return panel

    # ------------------------------------------------------------------
    # Config change handler
    # ------------------------------------------------------------------

    def _on_config_changed(self) -> None:
        valid = self._config.has_valid_path
        self._optimize_btn.setEnabled(valid)

        if valid:
            self._preview_timer.start()
        else:
            self._preview_timer.stop()
            self._preview_gen += 1
            if self._preview_changes:
                self._preview_changes = []
                self._update_preview()
            else:
                self._empty_label.setText(tr("opt_preview_empty"))
                self._empty_label.setVisible(True)
                self._preview_scroll.setVisible(False)
                self._changes_badge.setVisible(False)
                self._progress_bar.setVisible(False)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _refresh_preview(self) -> None:
        if not self._config.has_valid_path:
            self._preview_changes = []
            self._update_preview()
            return

        self._preview_gen += 1
        gen = self._preview_gen

        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)

        thread = QThread()
        worker = _PreviewWorker(
            gen,
            Path(self._config.file_path),
            self._config.get_scope(),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            self._on_preview_done, Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.progress.connect(
            self._on_preview_progress, Qt.ConnectionType.QueuedConnection,
        )

        pair = (thread, worker)
        self._active_threads.append(pair)
        thread.finished.connect(
            lambda p=pair: (
                self._active_threads.remove(p)
                if p in self._active_threads
                else None
            ),
        )

        thread.start()

    @Slot(int, object)
    def _on_preview_done(self, gen: int, changes: object) -> None:
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
        """Rebuild the preview panel from current changes."""
        old = self._preview_scroll.takeWidget()
        if old:
            old.deleteLater()

        self._preview_container = QWidget()
        self._preview_container.setStyleSheet(
            "background: transparent; border: none;"
        )
        self._preview_layout = QVBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(20, 20, 20, 20)
        self._preview_layout.setSpacing(10)
        self._preview_scroll.setWidget(self._preview_container)

        changes = self._preview_changes
        has_path = bool(self._config.file_path)

        if not has_path:
            self._empty_label.setText(tr("opt_preview_empty"))
            self._empty_label.setVisible(True)
            self._preview_scroll.setVisible(False)
            self._console.setVisible(False)
            self._changes_badge.setVisible(False)
            return

        if not changes:
            self._empty_label.setText(tr("opt_preview_clean"))
            self._empty_label.setVisible(True)
            self._preview_scroll.setVisible(False)
            self._console.setVisible(False)
            self._changes_badge.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._preview_scroll.setVisible(True)
        self._console.setVisible(False)

        file_count = len({c.file_path for c in changes})
        self._changes_badge.setText(
            tr("opt_changes_summary", count=len(changes), files=file_count),
        )
        self._changes_badge.setVisible(True)

        # Group by source_label
        by_source: dict[str, list[IncludeChange]] = {}
        for c in changes:
            by_source.setdefault(c.source_label, []).append(c)

        has_plugins = any(k != "" for k in by_source)

        if has_plugins:
            # Render as source groups (project + each plugin)
            # Project first
            if "" in by_source:
                w = _SourceGroup("", by_source[""], expanded=True)
                self._preview_layout.addWidget(w)
            # Then plugins sorted by name
            for label in sorted(k for k in by_source if k != ""):
                w = _SourceGroup(label, by_source[label], expanded=True)
                self._preview_layout.addWidget(w)
        else:
            # No plugins — flat category view (original behaviour)
            categories: dict[str, list[IncludeChange]] = {}
            for c in changes:
                categories.setdefault(c.category, []).append(c)
            for i, (cat_name, cat_changes) in enumerate(categories.items()):
                w = _PreviewCategory(
                    cat_name, cat_changes, expanded=(i < 3),
                )
                self._preview_layout.addWidget(w)

        self._preview_layout.addStretch()

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _execute_optimize(self) -> None:
        if not self._config.has_valid_path:
            return

        changes_count = len(self._preview_changes)
        result = MessageDialog.question(
            self,
            tr("opt_execute"),
            tr("opt_confirm", count=changes_count),
            [tr("no"), tr("yes")],
        )
        if result != tr("yes"):
            return

        self._empty_label.setVisible(False)
        self._preview_scroll.setVisible(False)
        self._console.setVisible(True)
        self._console.clear()
        self._optimize_btn.setEnabled(False)
        self.status_changed.emit("running", tr("opt_in_progress"))

        self._exec_thread = QThread()
        self._exec_worker = _ExecuteWorker(
            Path(self._config.file_path),
            self._config.get_scope(),
        )
        self._exec_worker.moveToThread(self._exec_thread)
        self._exec_thread.started.connect(self._exec_worker.run)
        self._exec_worker.finished.connect(
            self._on_exec_done, Qt.ConnectionType.QueuedConnection,
        )
        self._exec_worker.finished.connect(self._exec_thread.quit)
        self._exec_worker.log_message.connect(
            self._on_log_message,
            Qt.ConnectionType.QueuedConnection,
        )
        self._exec_thread.start()

    @Slot(object)
    def _on_exec_done(self, result: OptimizeResult) -> None:
        self._optimize_btn.setEnabled(True)
        if result.status == OptimizeStatus.SUCCESS and not result.errors:
            self.status_changed.emit("success", tr("success"))
            MessageDialog.information(
                self,
                tr("opt_complete"),
                tr(
                    "opt_successful",
                    count=result.changes_applied,
                    files=result.files_modified,
                    time=result.duration_seconds,
                ),
            )
        else:
            self.status_changed.emit("failed", tr("failed"))
            summary = (
                "\n".join(result.errors[:5]) if result.errors else result.message
            )
            MessageDialog.error(
                self, tr("opt_failed"), tr("opt_failed_msg", error=summary),
            )

    # ------------------------------------------------------------------
    # Host interface
    # ------------------------------------------------------------------

    def get_settings_tabs(self) -> list:
        return []

    def can_close(self) -> bool:
        if self._exec_thread and self._exec_thread.isRunning():
            result = MessageDialog.question(
                self,
                tr("opt_in_progress"),
                tr("opt_cancel_and_exit"),
                [tr("no"), tr("yes")],
            )
            return result == tr("yes")
        return True

    def cleanup(self) -> None:
        self._preview_gen += 1
        try:
            if self._exec_thread is not None and self._exec_thread.isRunning():
                self._exec_thread.quit()
                self._exec_thread.wait(3000)
        except RuntimeError:
            pass