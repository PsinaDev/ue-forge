"""
Commandlet Runner page for UE Forge.

Discovers commandlets from engine and project sources, provides
parameter editing, description display, and execution with live output.

Left panel: project selection, searchable commandlet list.
Right panel: commandlet info, parameters, console output.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

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
    QPlainTextEdit,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject, QSize

from framekit.styles import COLORS, FONTS, RADIUS
from framekit.icons import Icons
from framekit.widgets import PathInput, ConsoleWidget
from framekit.dialogs import MessageDialog
from framekit.types import LogLevel, LogMessage, StatusKind
from framekit.localization import tr
from pyside_frameless import DropZoneWidget

from ue_forge.config import get_ue_config_manager as get_config_manager

from .core import (
    CommandletInfo,
    CommandletParam,
    CommandletSource,
    RunResult,
    RunStatus,
    scan_directory,
    resolve_engine_path,
    get_editor_cmd_path,
    build_command,
    run_commandlet,
)


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class _ScanWorker(QObject):
    """Background worker for scanning engine/project source for commandlets."""

    finished = Signal(int, object, object)  # (gen, engine_list, project_list)
    progress = Signal(int)

    def __init__(
        self,
        gen: int,
        engine_source: Optional[Path],
        project_source: Optional[Path],
    ) -> None:
        super().__init__()
        self._gen = gen
        self._engine_source = engine_source
        self._project_source = project_source

    def run(self) -> None:
        engine_cmds: list[CommandletInfo] = []
        project_cmds: list[CommandletInfo] = []

        def prog(v: int) -> None:
            self.progress.emit(v)

        if self._engine_source and self._engine_source.is_dir():
            engine_cmds = scan_directory(
                self._engine_source, CommandletSource.ENGINE, prog,
            )

        if self._project_source and self._project_source.is_dir():
            project_cmds = scan_directory(
                self._project_source, CommandletSource.PROJECT, prog,
            )

        self.finished.emit(self._gen, engine_cmds, project_cmds)


class _RunWorker(QObject):
    """Background worker for executing a commandlet."""

    finished = Signal(object)  # RunResult
    log_message = Signal(object)  # LogMessage

    def __init__(
        self,
        editor_cmd: Path,
        project_path: Path,
        commandlet_name: str,
        params: list[str],
    ) -> None:
        super().__init__()
        self._editor_cmd = editor_cmd
        self._project_path = project_path
        self._commandlet_name = commandlet_name
        self._params = params
        self._cancelled = False
        self._process = None  # subprocess reference for force-kill

    def run(self) -> None:
        cb = lambda msg: self.log_message.emit(msg)
        result = run_commandlet(
            self._editor_cmd,
            self._project_path,
            self._commandlet_name,
            self._params,
            log_callback=cb,
            cancel_check=lambda: self._cancelled,
            process_holder=self,
        )
        self.finished.emit(result)

    def cancel(self) -> None:
        self._cancelled = True
        # Force-kill the subprocess if stdout iteration is blocking
        if self._process is not None:
            try:
                self._process.kill()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Commandlet list item with inline star
# ---------------------------------------------------------------------------

class _CommandletListItem(QListWidgetItem):
    """List item storing CommandletInfo reference."""

    def __init__(self, info: CommandletInfo) -> None:
        super().__init__()
        self.info = info
        source_tag = "E" if info.source == CommandletSource.ENGINE else "P"
        self.setToolTip(
            f"[{source_tag}] {info.class_name}\n{info.source_file}"
        )
        self.setSizeHint(QSize(0, 30))


class _CommandletItemWidget(QWidget):
    """Custom widget for list row: star button + source icon + name."""

    def __init__(
        self,
        info: CommandletInfo,
        is_favorite: bool,
        toggle_callback,
        list_widget: QListWidget,
        item: QListWidgetItem,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.info = info
        self._toggle_cb = toggle_callback
        self._is_fav = is_favorite
        self._list_widget = list_widget
        self._item = item

        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 8, 0)
        layout.setSpacing(4)

        # Star toggle
        self._star = QPushButton()
        self._star.setFixedSize(20, 20)
        self._star.setCursor(Qt.CursorShape.PointingHandCursor)
        self._star.clicked.connect(self._on_star)
        self._update_star()
        layout.addWidget(self._star)

        # Source icon + name
        source = "⚙" if info.source == CommandletSource.ENGINE else "📦"
        label = QLabel(f"{source}  {info.name}")
        label.setStyleSheet(
            f"color: {COLORS['text_secondary']};"
            f" font-size: {FONTS['size_sm']};"
            " background: transparent; border: none;"
        )
        layout.addWidget(label, 1)

        # Tooltip: class name + source file + description snippet
        tip_parts = [info.class_name, info.source_file]
        if info.description:
            # First 120 chars of description
            snippet = info.description[:120]
            if len(info.description) > 120:
                snippet += "…"
            tip_parts.append("")
            tip_parts.append(snippet)
        elif info.auto_usage:
            tip_parts.append("")
            tip_parts.append(info.auto_usage)
        self.setToolTip("\n".join(tip_parts))

    def mousePressEvent(self, event) -> None:
        """Forward clicks to select the list item."""
        self._list_widget.setCurrentItem(self._item)
        super().mousePressEvent(event)

    def _on_star(self) -> None:
        self._is_fav = self._toggle_cb(self.info.name)
        self._update_star()

    def _update_star(self) -> None:
        color = COLORS["warning"] if self._is_fav else COLORS["bg_hover"]
        self._star.setIcon(Icons.get_icon("STAR", 12, color))
        self._star.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 3px; padding: 2px;
            }}
            QPushButton:hover {{ background-color: {COLORS['bg_tertiary']}; }}
        """)


# ---------------------------------------------------------------------------
# Parameter field widget
# ---------------------------------------------------------------------------

class _ParamField(QWidget):
    """Single parameter row: checkbox + name + optional value input."""

    def __init__(
        self, param: CommandletParam, parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.param = param
        self.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self._check = QCheckBox()
        self._check.setFixedWidth(24)
        layout.addWidget(self._check)

        name_label = QLabel(f"-{param.name}")
        name_label.setStyleSheet(
            f"color: {COLORS['accent_primary']};"
            f" font-family: {FONTS['family_mono']};"
            f" font-size: {FONTS['size_sm']};"
            " background: transparent; border: none;"
        )
        name_label.setFixedWidth(180)
        layout.addWidget(name_label)

        if param.has_value:
            self._value = QLineEdit()
            self._value.setPlaceholderText(param.default_value or "value...")
            self._value.setFixedHeight(30)
            self._value.setStyleSheet(f"font-family: {FONTS['family_mono']};")
            if param.default_value:
                self._value.setText(param.default_value)
            layout.addWidget(self._value, 1)
        else:
            self._value = None
            layout.addStretch()

        if param.description:
            desc = QLabel(param.description)
            desc.setStyleSheet(
                f"color: {COLORS['text_dim']};"
                f" font-size: {FONTS['size_xs']};"
                " background: transparent; border: none;"
            )
            desc.setWordWrap(True)
            layout.addWidget(desc)

    @property
    def is_enabled(self) -> bool:
        return self._check.isChecked()

    def get_param_string(self) -> str:
        """Return the parameter as a command-line string."""
        if not self.is_enabled:
            return ""
        if self._value and self._value.text().strip():
            return f"-{self.param.name}={self._value.text().strip()}"
        return f"-{self.param.name}"


# ---------------------------------------------------------------------------
# Left config panel
# ---------------------------------------------------------------------------

class _ConfigPanel(DropZoneWidget):
    """Left panel: project selection, commandlet list."""

    config_changed = Signal()
    commandlet_selected = Signal(object)  # CommandletInfo or None

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(
            parent,
            valid_extensions=[".uproject"],
            allow_directories=True,
        )
        self._engine_path: Optional[Path] = None
        self._all_commandlets: list[CommandletInfo] = []
        self._selected: Optional[CommandletInfo] = None
        self._favorites: set[str] = get_config_manager().load_favorites()
        self._setup_ui()
        overlay = self.setup_drop_overlay()
        overlay.configure(
            valid_pixmap=Icons.get_pixmap(
                "UPLOAD", 48, "rgba(34, 211, 238, 1)",
            ),
            invalid_pixmap=Icons.get_pixmap(
                "X_CIRCLE", 48, "rgba(248, 113, 113, 1)",
            ),
            invalid_text=tr("cmd_invalid_drop"),
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
            Icons.get_pixmap("TERMINAL", 20, COLORS["accent_primary"]),
        )
        hdr_icon.setFixedSize(20, 20)
        hdr.addWidget(hdr_icon)
        hdr_title = QLabel(tr("cmd_title"))
        hdr_title.setStyleSheet(
            f"color: {COLORS['text_primary']};"
            f" font-size: {FONTS['size_xl']}; font-weight: 600;"
        )
        hdr.addWidget(hdr_title)
        hdr.addStretch()
        cl.addLayout(hdr)

        # Description
        desc = QLabel(tr("cmd_description"))
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {COLORS['text_muted']};"
            f" font-size: {FONTS['size_sm']};"
        )
        cl.addWidget(desc)

        # Project path
        self._file_input = PathInput(
            label=tr("cmd_select_project"),
            placeholder=tr("cmd_path_placeholder"),
            hint=tr("cmd_drag_drop_hint"),
            icon_name="FOLDER_OPEN",
            file_filter="UE Project (*.uproject)",
        )
        self._file_input.path_changed.connect(self._on_path_changed)
        cl.addWidget(self._file_input)

        # Engine info badge
        self._engine_label = QLabel()
        self._engine_label.setStyleSheet(
            f"color: {COLORS['text_dim']};"
            f" font-size: {FONTS['size_xs']};"
            " background: transparent; border: none;"
        )
        self._engine_label.setVisible(False)
        cl.addWidget(self._engine_label)

        # Commandlet list card
        list_card = self._card()
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(8)

        # Card header
        list_hdr = QHBoxLayout()
        list_hdr.setSpacing(6)
        list_icon = QLabel()
        list_icon.setPixmap(
            Icons.get_pixmap("TERMINAL", 14, COLORS["accent_primary"]),
        )
        list_icon.setFixedSize(14, 14)
        list_hdr.addWidget(list_icon)
        list_title = QLabel(tr("cmd_commandlets"))
        list_title.setStyleSheet(
            f"color: {COLORS['text_secondary']};"
            f" font-size: {FONTS['size_sm']}; font-weight: 500;"
        )
        list_hdr.addWidget(list_title)
        list_hdr.addStretch()

        self._count_label = QLabel()
        self._count_label.setStyleSheet(
            f"color: {COLORS['text_dim']};"
            f" font-size: {FONTS['size_xs']};"
            " background: transparent; border: none;"
        )
        list_hdr.addWidget(self._count_label)
        list_layout.addLayout(list_hdr)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("cmd_search_placeholder"))
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(34)
        self._search.textChanged.connect(self._filter_list)
        list_layout.addWidget(self._search)

        # Commandlet list
        self._cmd_list = QListWidget()
        self._cmd_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self._cmd_list.setMinimumHeight(200)
        self._cmd_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_primary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-radius: {RADIUS['md']};
                color: {COLORS['text_secondary']};
                font-size: {FONTS['size_sm']};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['accent_bg']};
                color: {COLORS['text_primary']};
            }}
            QListWidget::item:hover {{
                background-color: rgba(39, 39, 42, 0.7);
            }}
        """)
        self._cmd_list.currentItemChanged.connect(self._on_item_changed)
        list_layout.addWidget(self._cmd_list)

        # Source filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self._filter_engine = QCheckBox(tr("cmd_filter_engine"))
        self._filter_engine.setChecked(True)
        self._filter_engine.stateChanged.connect(self._filter_list)
        filter_row.addWidget(self._filter_engine)

        self._filter_project = QCheckBox(tr("cmd_filter_project"))
        self._filter_project.setChecked(True)
        self._filter_project.stateChanged.connect(self._filter_list)
        filter_row.addWidget(self._filter_project)

        self._filter_favorites = QCheckBox("★")
        self._filter_favorites.setToolTip(tr("cmd_filter_favorites"))
        self._filter_favorites.stateChanged.connect(self._filter_list)
        filter_row.addWidget(self._filter_favorites)

        filter_row.addStretch()
        list_layout.addLayout(filter_row)

        cl.addWidget(list_card)
        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("cmdCard")
        f.setStyleSheet(f"""
            QFrame#cmdCard {{
                background-color: rgba(24, 24, 27, 0.3);
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
        """)
        return f

    # Properties

    @property
    def project_path(self) -> str:
        return self._file_input.path()

    @property
    def engine_path(self) -> Optional[Path]:
        return self._engine_path

    @property
    def selected_commandlet(self) -> Optional[CommandletInfo]:
        return self._selected

    # Public methods

    def set_commandlets(
        self,
        engine: list[CommandletInfo],
        project: list[CommandletInfo],
    ) -> None:
        """Populate the commandlet list from scan results."""
        self._all_commandlets = sorted(
            engine + project,
            key=lambda c: (c.source != CommandletSource.PROJECT, c.name.lower()),
        )
        self._filter_list()
        total = len(self._all_commandlets)
        eng = len(engine)
        proj = len(project)
        self._count_label.setText(
            tr("cmd_count", total=total, engine=eng, project=proj),
        )

    def is_favorite(self, name: str) -> bool:
        return name in self._favorites

    def toggle_favorite(self, name: str) -> bool:
        """Toggle favorite status. Returns new state.

        Does NOT rebuild the list — the calling widget updates its own
        star icon.  Sort order refreshes on next filter/scan.
        """
        is_fav = get_config_manager().toggle_favorite(name)
        if is_fav:
            self._favorites.add(name)
        else:
            self._favorites.discard(name)
        return is_fav

    # Handlers

    def _on_file_dropped(self, path: str) -> None:
        self._file_input.set_path(path)

    def _on_path_changed(self, path: str) -> None:
        if path:
            p = Path(path)
            # If directory was dropped, look for .uproject inside
            if p.is_dir():
                for f in p.iterdir():
                    if f.suffix == ".uproject":
                        self._file_input.set_path(str(f))
                        return

            if p.suffix == ".uproject" and p.exists():
                self._engine_path = resolve_engine_path(p)
                if self._engine_path:
                    # Extract version
                    from ue_forge.plugin_builder.engine_finder import EngineFinder
                    finder = EngineFinder()
                    ver = finder.extract_version(self._engine_path)
                    self._engine_label.setText(
                        tr("cmd_engine_detected", version=ver or "?",
                           path=str(self._engine_path)),
                    )
                    self._engine_label.setStyleSheet(
                        f"color: {COLORS['success']};"
                        f" font-size: {FONTS['size_xs']};"
                        " background: transparent; border: none;"
                    )
                else:
                    self._engine_label.setText(tr("cmd_engine_not_found"))
                    self._engine_label.setStyleSheet(
                        f"color: {COLORS['warning']};"
                        f" font-size: {FONTS['size_xs']};"
                        " background: transparent; border: none;"
                    )
                self._engine_label.setVisible(True)
            else:
                self._engine_path = None
                self._engine_label.setVisible(False)
        else:
            self._engine_path = None
            self._engine_label.setVisible(False)

        self.config_changed.emit()

    def _on_item_changed(
        self,
        current: Optional[QListWidgetItem],
        _previous: Optional[QListWidgetItem],
    ) -> None:
        if current and isinstance(current, _CommandletListItem):
            self._selected = current.info
        else:
            self._selected = None
        self.commandlet_selected.emit(self._selected)

    def _filter_list(self) -> None:
        """Rebuild visible list based on search text, source and favorites filters."""
        search = self._search.text().strip().lower()
        show_engine = self._filter_engine.isChecked()
        show_project = self._filter_project.isChecked()
        only_favorites = self._filter_favorites.isChecked()

        self._cmd_list.blockSignals(True)
        self._cmd_list.clear()

        # Sort: favorites first, then by name
        sorted_cmds = sorted(
            self._all_commandlets,
            key=lambda c: (
                c.name not in self._favorites,
                c.source != CommandletSource.PROJECT,
                c.name.lower(),
            ),
        )

        for info in sorted_cmds:
            if info.source == CommandletSource.ENGINE and not show_engine:
                continue
            if info.source == CommandletSource.PROJECT and not show_project:
                continue
            if only_favorites and info.name not in self._favorites:
                continue
            if search and search not in info.name.lower():
                continue

            item = _CommandletListItem(info)
            self._cmd_list.addItem(item)

            is_fav = info.name in self._favorites
            widget = _CommandletItemWidget(
                info, is_fav, self.toggle_favorite,
                self._cmd_list, item,
            )
            self._cmd_list.setItemWidget(item, widget)

        self._cmd_list.blockSignals(False)

        # Restore selection if still visible
        if self._selected:
            for i in range(self._cmd_list.count()):
                it = self._cmd_list.item(i)
                if isinstance(it, _CommandletListItem) and it.info is self._selected:
                    self._cmd_list.setCurrentItem(it)
                    break


# ---------------------------------------------------------------------------
# Right detail/execution panel
# ---------------------------------------------------------------------------

class _DetailPanel(QWidget):
    """Right panel: commandlet info, parameters, console, run button."""

    run_requested = Signal()
    show_command_requested = Signal()
    cancel_requested = Signal()
    favorite_toggled = Signal(str)  # commandlet name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current: Optional[CommandletInfo] = None
        self._is_favorite: bool = False
        self._param_fields: list[_ParamField] = []
        # Running state
        self._is_running: bool = False
        self._running_commandlet_name: str = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setObjectName("cmdDetailHeader")
        header.setFixedHeight(40)
        header.setStyleSheet(f"""
            QFrame#cmdDetailHeader {{
                background: {COLORS['bg_secondary']};
                border: none;
                border-bottom: 1px solid {COLORS['border_default']};
            }}
        """)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(8)

        hi = QLabel()
        hi.setPixmap(
            Icons.get_pixmap("TERMINAL", 16, COLORS["accent_primary"]),
        )
        hi.setFixedSize(16, 16)
        hl.addWidget(hi)

        self._header_title = QLabel(tr("cmd_details"))
        self._header_title.setStyleSheet(
            f"color: {COLORS['text_primary']};"
            f" font-size: {FONTS['size_sm']}; font-weight: 600;"
        )
        hl.addWidget(self._header_title)

        # Star / favorite button
        self._star_btn = QPushButton()
        self._star_btn.setFixedSize(24, 24)
        self._star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._star_btn.setVisible(False)
        self._star_btn.clicked.connect(self._on_star_clicked)
        self._update_star_icon()
        hl.addWidget(self._star_btn)

        hl.addStretch()

        self._source_badge = QLabel()
        self._source_badge.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: {FONTS['size_xs']};"
            " background: transparent; border: none;"
        )
        self._source_badge.setVisible(False)
        hl.addWidget(self._source_badge)

        # Back to console button (visible when running and viewing details)
        self._back_to_console_btn = QPushButton()
        self._back_to_console_btn.setIcon(
            Icons.get_icon("ARROW_LEFT", 14, COLORS["accent_primary"])
        )
        self._back_to_console_btn.setText(tr("cmd_back_to_console"))
        self._back_to_console_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_tertiary']};
                border: 1px solid {COLORS['accent_primary']};
                border-radius: 4px;
                padding: 4px 8px;
                color: {COLORS['accent_primary']};
                font-size: {FONTS['size_xs']};
            }}
            QPushButton:hover {{
                background: {COLORS['accent_primary']};
                color: {COLORS['bg_primary']};
            }}
        """)
        self._back_to_console_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_to_console_btn.setVisible(False)
        self._back_to_console_btn.clicked.connect(self._on_back_to_console)
        hl.addWidget(self._back_to_console_btn)

        layout.addWidget(header)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # Content stack: empty state / detail scroll / console
        self._empty_label = QLabel(tr("cmd_empty"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {COLORS['text_dim']};"
            f" font-size: {FONTS['size_sm']};"
        )

        # Scrollable detail area
        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )
        self._detail_scroll.setVisible(False)

        self._detail_container = QWidget()
        self._detail_container.setStyleSheet(
            "background: transparent; border: none;"
        )
        self._detail_layout = QVBoxLayout(self._detail_container)
        self._detail_layout.setContentsMargins(20, 20, 20, 20)
        self._detail_layout.setSpacing(16)
        self._detail_scroll.setWidget(self._detail_container)

        # Console
        self._console = ConsoleWidget()
        self._console.setVisible(False)

        layout.addWidget(self._empty_label, 1)
        layout.addWidget(self._detail_scroll, 1)
        layout.addWidget(self._console, 1)

        # Bottom control bar
        controls = QFrame()
        controls.setObjectName("cmdControls")
        controls.setFixedHeight(64)
        controls.setStyleSheet(f"""
            QFrame#cmdControls {{
                background: rgba(24, 24, 27, 0.5);
                border: none;
                border-top: 1px solid {COLORS['border_default']};
            }}
        """)
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(16, 0, 16, 0)
        cl.setSpacing(12)

        # Dry run checkbox
        self._dry_run = QCheckBox(tr("cmd_dry_run"))
        self._dry_run.setToolTip(tr("cmd_dry_run_desc"))
        cl.addWidget(self._dry_run)

        # Show command button
        self._show_cmd_btn = QPushButton(f"  {tr('show_command')}")
        self._show_cmd_btn.setIcon(Icons.get_icon("TERMINAL", 14, COLORS["text_dim"]))
        self._show_cmd_btn.setCursor(Qt.PointingHandCursor)
        self._show_cmd_btn.setEnabled(False)
        self._show_cmd_btn.clicked.connect(self._show_command)
        cl.addWidget(self._show_cmd_btn)

        cl.addStretch()

        self._cancel_btn = QPushButton(f"  {tr('cancel')}")
        self._cancel_btn.setIcon(Icons.get_icon("X", 14, COLORS["error"]))
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                border-color: {COLORS['error']};
                color: {COLORS['error']};
            }}
            QPushButton:hover {{
                background-color: {COLORS['error_bg']};
            }}
        """)
        self._cancel_btn.setFixedHeight(40)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)
        cl.addWidget(self._cancel_btn)

        self._run_btn = QPushButton(f"  {tr('cmd_run')}")
        self._run_btn.setIcon(Icons.get_icon("PLAY", 16, "#ffffff"))
        self._run_btn.setProperty("class", "primary")
        self._run_btn.setFixedWidth(180)
        self._run_btn.setFixedHeight(40)
        self._run_btn.setCursor(Qt.PointingHandCursor)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run_clicked)
        cl.addWidget(self._run_btn)

        layout.addWidget(controls)

    def _card(self) -> QFrame:
        f = QFrame()
        f.setObjectName("cmdDetailCard")
        f.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        f.setStyleSheet(f"""
            QFrame#cmdDetailCard {{
                background-color: rgba(24, 24, 27, 0.3);
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
        """)
        return f

    # Public interface

    @property
    def console(self) -> ConsoleWidget:
        return self._console

    @property
    def dry_run(self) -> bool:
        return self._dry_run.isChecked()

    @property
    def run_button(self) -> QPushButton:
        return self._run_btn

    @property
    def progress_bar(self) -> QProgressBar:
        return self._progress_bar

    def set_commandlet(
        self, info: Optional[CommandletInfo], is_favorite: bool = False,
    ) -> None:
        """Display details for the selected commandlet."""
        # Skip rebuild if same commandlet already shown
        if info is self._current:
            return

        # Flush pending note save for previous commandlet
        if hasattr(self, '_notes_save_timer') and self._notes_save_timer.isActive():
            self._notes_save_timer.stop()
            # Save now — widget still alive before deleteLater
            if self._current and hasattr(self, '_notes_edit'):
                get_config_manager().save_note(
                    self._current.name, self._notes_edit.toPlainText(),
                )

        self._current = info
        self._is_favorite = is_favorite

        if not info:
            self._empty_label.setVisible(True)
            self._detail_scroll.setVisible(False)
            self._console.setVisible(False)
            self._run_btn.setEnabled(False)
            self._show_cmd_btn.setEnabled(False)
            self._source_badge.setVisible(False)
            self._star_btn.setVisible(False)
            self._header_title.setText(tr("cmd_details"))
            return

        self._header_title.setText(info.name)
        self._star_btn.setVisible(True)
        self._update_star_icon()
        source_text = (
            tr("cmd_source_engine") if info.source == CommandletSource.ENGINE
            else tr("cmd_source_project")
        )
        self._source_badge.setText(source_text)
        self._source_badge.setVisible(True)

        # Rebuild detail content
        old = self._detail_scroll.takeWidget()
        if old:
            old.deleteLater()

        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Source file path + Open button
        src_row = QHBoxLayout()
        src_row.setSpacing(6)
        src_label = QLabel(info.source_file)
        src_label.setStyleSheet(
            f"color: {COLORS['text_dim']};"
            f" font-family: {FONTS['family_mono']};"
            f" font-size: 10px;"
            " background: transparent; border: none;"
        )
        src_row.addWidget(src_label, 1)

        if info.source_path:
            open_btn = QPushButton()
            open_btn.setIcon(Icons.get_icon("FOLDER_OPEN", 12, COLORS["text_dim"]))
            open_btn.setToolTip(tr("cmd_open_source"))
            open_btn.setFixedSize(22, 22)
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    border-radius: 4px; padding: 3px;
                }}
                QPushButton:hover {{ background-color: {COLORS['bg_tertiary']}; }}
            """)
            path_to_open = info.source_path
            open_btn.clicked.connect(
                lambda _=False, p=path_to_open: self._open_file(p),
            )
            src_row.addWidget(open_btn)

        lay.addLayout(src_row)

        # Description card — with internal scroll for long text
        has_desc = info.description or info.help_text
        auto_usage = info.auto_usage
        if has_desc or auto_usage:
            desc_card = self._card()
            desc_lay = QVBoxLayout(desc_card)
            desc_lay.setContentsMargins(16, 12, 16, 12)
            desc_lay.setSpacing(6)

            desc_hdr = QHBoxLayout()
            desc_hdr.setSpacing(6)
            di = QLabel()
            di.setPixmap(
                Icons.get_pixmap("FILE_CODE", 14, COLORS["accent_primary"]),
            )
            di.setFixedSize(14, 14)
            desc_hdr.addWidget(di)
            dt = QLabel(tr("description"))
            dt.setStyleSheet(
                f"color: {COLORS['text_secondary']};"
                f" font-size: {FONTS['size_sm']}; font-weight: 500;"
            )
            desc_hdr.addWidget(dt)
            desc_hdr.addStretch()
            desc_lay.addLayout(desc_hdr)

            # Scrollable content inside description card
            desc_scroll = QScrollArea()
            desc_scroll.setWidgetResizable(True)
            desc_scroll.setMaximumHeight(180)
            desc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            desc_scroll.setStyleSheet(
                "QScrollArea { background: transparent; border: none; padding: 0; }"
            )
            desc_inner = QWidget()
            desc_inner.setStyleSheet("background: transparent;")
            desc_inner_lay = QVBoxLayout(desc_inner)
            desc_inner_lay.setContentsMargins(0, 0, 0, 0)
            desc_inner_lay.setSpacing(4)

            if info.description:
                desc_text = QLabel(info.description)
                desc_text.setWordWrap(True)
                desc_text.setStyleSheet(
                    f"color: {COLORS['text_muted']};"
                    f" font-size: {FONTS['size_sm']};"
                    " background: transparent; border: none;"
                )
                desc_inner_lay.addWidget(desc_text)

            if info.help_text:
                help_label = QLabel(info.help_text)
                help_label.setWordWrap(True)
                help_label.setStyleSheet(
                    f"color: {COLORS['text_dim']};"
                    f" font-family: {FONTS['family_mono']};"
                    f" font-size: {FONTS['size_xs']};"
                    " background: transparent; border: none;"
                )
                desc_inner_lay.addWidget(help_label)

            if auto_usage:
                usage_label = QLabel(auto_usage)
                usage_label.setWordWrap(True)
                usage_label.setStyleSheet(
                    f"color: {COLORS['accent_primary']};"
                    f" font-family: {FONTS['family_mono']};"
                    f" font-size: {FONTS['size_xs']};"
                    " background: transparent; border: none;"
                )
                desc_inner_lay.addWidget(usage_label)

            # Show usage examples from .cpp comments
            if info.examples:
                examples_header = QLabel(tr("cmd_examples"))
                examples_header.setStyleSheet(
                    f"color: {COLORS['text_secondary']};"
                    f" font-size: {FONTS['size_xs']};"
                    " font-weight: 500;"
                    " background: transparent; border: none;"
                    " margin-top: 8px;"
                )
                desc_inner_lay.addWidget(examples_header)

                for example in info.examples[:3]:  # Limit to 3 examples
                    ex_label = QLabel(example)
                    ex_label.setWordWrap(True)
                    ex_label.setTextInteractionFlags(
                        Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
                    )
                    ex_label.setStyleSheet(
                        f"color: {COLORS['text_dim']};"
                        f" font-family: {FONTS['family_mono']};"
                        f" font-size: {FONTS['size_xs']};"
                        " background: transparent; border: none;"
                        " padding-left: 8px;"
                    )
                    desc_inner_lay.addWidget(ex_label)

            desc_scroll.setWidget(desc_inner)
            desc_lay.addWidget(desc_scroll)
            lay.addWidget(desc_card)

        # Notes card — same structure as Parameters card
        notes_card = self._card()
        notes_lay = QVBoxLayout(notes_card)
        notes_lay.setContentsMargins(16, 12, 16, 12)
        notes_lay.setSpacing(6)

        notes_hdr = QHBoxLayout()
        notes_hdr.setSpacing(6)
        ni = QLabel()
        ni.setPixmap(Icons.get_pixmap("FILE_CODE", 14, COLORS["warning"]))
        ni.setFixedSize(14, 14)
        notes_hdr.addWidget(ni)
        nt = QLabel(tr("cmd_notes"))
        nt.setStyleSheet(
            f"color: {COLORS['text_secondary']};"
            f" font-size: {FONTS['size_sm']}; font-weight: 500;"
        )
        notes_hdr.addWidget(nt)
        notes_hdr.addStretch()
        notes_lay.addLayout(notes_hdr)

        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setPlaceholderText(tr("cmd_notes_placeholder"))
        self._notes_edit.setMinimumHeight(36)
        self._notes_edit.setMaximumHeight(120)
        self._notes_edit.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
                padding: 8px;
                color: {COLORS['text_primary']};
                font-size: {FONTS['size_xs']};
            }}
            QPlainTextEdit:focus {{
                border-color: {COLORS['border_focus']};
            }}
        """)
        existing = get_config_manager().get_note(info.name)
        if existing:
            self._notes_edit.setPlainText(existing)

        # Auto-resize to content
        def _adjust_notes_height() -> None:
            doc_h = int(self._notes_edit.document().size().height()) + 20
            self._notes_edit.setFixedHeight(
                max(36, min(doc_h, 120)),
            )
        self._notes_edit.textChanged.connect(_adjust_notes_height)
        _adjust_notes_height()
        self._notes_save_timer = QTimer()
        self._notes_save_timer.setSingleShot(True)
        self._notes_save_timer.setInterval(500)
        cmdlet_name = info.name
        self._notes_save_timer.timeout.connect(
            lambda: get_config_manager().save_note(
                cmdlet_name, self._notes_edit.toPlainText(),
            ),
        )
        self._notes_edit.textChanged.connect(
            lambda: self._notes_save_timer.start(),
        )
        notes_lay.addWidget(self._notes_edit)
        lay.addWidget(notes_card)

        # Parameters card
        params_card = self._card()
        params_lay = QVBoxLayout(params_card)
        params_lay.setContentsMargins(16, 12, 16, 12)
        params_lay.setSpacing(6)

        # Header
        params_hdr = QHBoxLayout()
        params_hdr.setSpacing(6)
        pi = QLabel()
        pi.setPixmap(
            Icons.get_pixmap("SETTINGS", 14, COLORS["accent_primary"]),
        )
        pi.setFixedSize(14, 14)
        params_hdr.addWidget(pi)
        pt = QLabel(tr("cmd_parameters"))
        pt.setStyleSheet(
            f"color: {COLORS['text_secondary']};"
            f" font-size: {FONTS['size_sm']}; font-weight: 500;"
        )
        params_hdr.addWidget(pt)
        params_hdr.addStretch()
        params_lay.addLayout(params_hdr)

        # Auto-discovered params or hint
        self._param_fields = []
        if info.params:
            for param in info.params:
                field = _ParamField(param)
                self._param_fields.append(field)
                params_lay.addWidget(field)
        else:
            no_params = QLabel(tr("cmd_no_params"))
            no_params.setStyleSheet(
                f"color: {COLORS['text_dim']};"
                f" font-size: {FONTS['size_xs']};"
                f" font-style: italic;"
                " background: transparent; border: none;"
                " padding: 0; margin: 0;"
            )
            params_lay.addWidget(no_params)

        # Separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(
            f"background: {COLORS['border_default']};"
            " border: none; margin: 2px 0;"
        )
        params_lay.addWidget(sep)

        # Custom parameters textarea
        custom_label = QLabel(tr("cmd_custom_params"))
        custom_label.setStyleSheet(
            f"color: {COLORS['text_dim']};"
            f" font-size: {FONTS['size_xs']};"
            " background: transparent; border: none;"
            " padding: 0; margin: 0;"
        )
        params_lay.addWidget(custom_label)

        self._custom_params = QPlainTextEdit()
        self._custom_params.setPlaceholderText(tr("cmd_custom_params_hint"))
        self._custom_params.setFixedHeight(80)
        self._custom_params.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
                padding: 8px;
                color: {COLORS['text_primary']};
                font-family: {FONTS['family_mono']};
                font-size: {FONTS['size_xs']};
            }}
            QPlainTextEdit:focus {{
                border-color: {COLORS['border_focus']};
            }}
        """)
        params_lay.addWidget(self._custom_params)

        lay.addWidget(params_card)

        self._detail_scroll.setWidget(container)
        self._empty_label.setVisible(False)
        self._detail_scroll.setVisible(True)
        self._console.setVisible(False)
        self._run_btn.setEnabled(True)
        self._show_cmd_btn.setEnabled(True)

        # Update back button visibility (show if a commandlet is running)
        self._update_back_button_visibility()

    def get_all_params(self) -> list[str]:
        """Collect all enabled parameters."""
        params: list[str] = []
        for field in self._param_fields:
            p = field.get_param_string()
            if p:
                params.append(p)

        custom = self._custom_params.toPlainText().strip()
        if custom:
            for line in custom.splitlines():
                line = line.strip()
                if line:
                    params.extend(line.split())

        if self._dry_run.isChecked():
            params.append("-WhatIf")

        return params

    def show_console(self, clear: bool = True) -> None:
        """Switch to console view.

        Args:
            clear: Whether to clear console content (True when starting new run,
                   False when returning to view running output)
        """
        self._empty_label.setVisible(False)
        self._detail_scroll.setVisible(False)
        self._console.setVisible(True)
        if clear:
            self._console.clear()
        self._update_back_button_visibility()

    def show_detail(self) -> None:
        """Switch back to detail view."""
        if self._current:
            self._empty_label.setVisible(False)
            self._detail_scroll.setVisible(True)
            self._console.setVisible(False)
        else:
            self._empty_label.setVisible(True)
            self._detail_scroll.setVisible(False)
            self._console.setVisible(False)
        self._update_back_button_visibility()

    def _on_run_clicked(self) -> None:
        self.run_requested.emit()

    def _on_cancel_clicked(self) -> None:
        self.cancel_requested.emit()

    def set_running(self, running: bool, commandlet_name: str = "") -> None:
        """Toggle UI between running and idle states."""
        self._is_running = running
        if running and commandlet_name:
            self._running_commandlet_name = commandlet_name
        elif not running:
            self._running_commandlet_name = ""

        self._run_btn.setEnabled(not running)
        self._run_btn.setVisible(not running)
        self._cancel_btn.setVisible(running)
        self._dry_run.setEnabled(not running)
        self._show_cmd_btn.setEnabled(not running)

        # Update back to console button visibility
        self._update_back_button_visibility()

    def _update_back_button_visibility(self) -> None:
        """Show 'back to console' button when running and viewing different commandlet."""
        if not self._is_running:
            self._back_to_console_btn.setVisible(False)
            return

        # Show button if we're running but console is not visible
        # (user clicked on a different commandlet during execution)
        showing_console = self._console.isVisible()
        self._back_to_console_btn.setVisible(not showing_console)

    def _on_back_to_console(self) -> None:
        """Return to console view showing running commandlet output."""
        self.show_console(clear=False)
        # Update header to show running commandlet name
        if self._running_commandlet_name:
            self._header_title.setText(self._running_commandlet_name)

    def _show_command(self) -> None:
        """Show the command that would be executed."""
        if not self._current:
            return
        self.show_command_requested.emit()

    def set_favorite(self, is_favorite: bool) -> None:
        """Update star icon without rebuilding the panel."""
        self._is_favorite = is_favorite
        self._update_star_icon()

    def _update_star_icon(self) -> None:
        color = COLORS["warning"] if self._is_favorite else COLORS["text_dim"]
        self._star_btn.setIcon(Icons.get_icon("STAR", 14, color))
        self._star_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                border-radius: 4px; padding: 4px;
            }}
            QPushButton:hover {{ background-color: {COLORS['bg_tertiary']}; }}
        """)

    def _on_star_clicked(self) -> None:
        if self._current:
            self.favorite_toggled.emit(self._current.name)

    @staticmethod
    def _open_file(path: str) -> None:
        """Open a file with the system default application."""
        import subprocess, sys
        p = Path(path)
        if not p.exists():
            return
        if sys.platform == "win32":
            import os
            os.startfile(str(p))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])


# ---------------------------------------------------------------------------
# CommandletRunnerPage
# ---------------------------------------------------------------------------

class CommandletRunnerPage(QWidget):
    """Commandlet Runner page matching project design language."""

    PAGE_ID = "commandlet_runner"
    PAGE_ICON = "TERMINAL"

    status_changed = Signal(object, str)

    LEFT_PANEL_WIDTH = 440

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._scan_gen: int = 0
        self._active_threads: list = []
        self._exec_thread: Optional[QThread] = None
        self._exec_worker: Optional[_RunWorker] = None

        self._setup_ui()
        self._config.config_changed.connect(self._on_config_changed)
        self._config.commandlet_selected.connect(self._on_commandlet_selected)
        self._detail.run_requested.connect(self._on_run_requested)
        self._detail.show_command_requested.connect(self._on_show_command)
        self._detail.cancel_requested.connect(self._on_cancel)
        self._detail.favorite_toggled.connect(self._on_favorite_toggled)

    @staticmethod
    def page_title() -> str:
        return tr("commandlet_launcher")

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

        self._detail = _DetailPanel()
        self._detail.setMinimumWidth(400)
        splitter.addWidget(self._detail)

        splitter.setSizes([self.LEFT_PANEL_WIDTH, 720])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.handle(1).setEnabled(False)
        splitter.handle(1).setCursor(Qt.CursorShape.ArrowCursor)

        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # Config change — trigger scan
    # ------------------------------------------------------------------

    def _on_config_changed(self) -> None:
        path = self._config.project_path
        engine = self._config.engine_path

        if path and engine:
            self._start_scan(Path(path), engine)
        elif not path:
            self._config.set_commandlets([], [])

    def _start_scan(self, project: Path, engine: Path) -> None:
        self._scan_gen += 1
        gen = self._scan_gen

        engine_source = engine / "Engine" / "Source"
        project_source = project.parent / "Source"

        if not engine_source.is_dir():
            engine_source = None
        if not project_source.is_dir():
            project_source = None

        if not engine_source and not project_source:
            return

        self._detail.progress_bar.setValue(0)
        self._detail.progress_bar.setVisible(True)

        thread = QThread()
        worker = _ScanWorker(gen, engine_source, project_source)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            self._on_scan_done, Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.progress.connect(
            self._on_scan_progress, Qt.ConnectionType.QueuedConnection,
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

    @Slot(int)
    def _on_scan_progress(self, value: int) -> None:
        """Receive progress from scan worker on the main thread."""
        self._detail.progress_bar.setValue(value)

    @Slot(int, object, object)
    def _on_scan_done(
        self,
        gen: int,
        engine_cmds: object,
        project_cmds: object,
    ) -> None:
        if gen != self._scan_gen:
            return
        self._detail.progress_bar.setVisible(False)
        self._config.set_commandlets(
            engine_cmds if engine_cmds else [],
            project_cmds if project_cmds else [],
        )
        total = len(engine_cmds or []) + len(project_cmds or [])
        if total:
            self.status_changed.emit(
                StatusKind.SUCCESS,
                tr("cmd_scan_done", count=total),
            )

    # ------------------------------------------------------------------
    # Commandlet selection
    # ------------------------------------------------------------------

    def _on_commandlet_selected(self, info: object) -> None:
        is_fav = self._config.is_favorite(info.name) if info else False
        self._detail.set_commandlet(info, is_favorite=is_fav)

    def _on_favorite_toggled(self, name: str) -> None:
        is_fav = self._config.toggle_favorite(name)
        self._detail.set_favorite(is_fav)
        # Sync the matching list item widget's star
        for i in range(self._config._cmd_list.count()):
            item = self._config._cmd_list.item(i)
            widget = self._config._cmd_list.itemWidget(item)
            if (isinstance(item, _CommandletListItem)
                    and item.info.name == name
                    and isinstance(widget, _CommandletItemWidget)):
                widget._is_fav = is_fav
                widget._update_star()
                break

    # ------------------------------------------------------------------
    # Show command
    # ------------------------------------------------------------------

    def _on_show_command(self) -> None:
        cmd_info = self._config.selected_commandlet
        if not cmd_info:
            return

        project = Path(self._config.project_path)
        engine = self._config.engine_path
        if not engine:
            MessageDialog.warning(
                self, tr("error"), tr("cmd_engine_not_found"),
            )
            return

        editor_cmd = get_editor_cmd_path(engine)
        if not editor_cmd:
            MessageDialog.warning(
                self, tr("error"), tr("cmd_editor_not_found"),
            )
            return

        params = self._detail.get_all_params()
        cmd = build_command(editor_cmd, project, cmd_info.name, params)
        cmd_str = " ".join(cmd)

        from ue_forge.plugin_builder.command_dialog import CommandDialog
        dlg = CommandDialog(self, cmd_str)
        dlg.exec()

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run_requested(self) -> None:
        cmd_info = self._config.selected_commandlet
        if not cmd_info:
            return

        project = Path(self._config.project_path)
        engine = self._config.engine_path
        if not engine:
            MessageDialog.warning(
                self, tr("error"), tr("cmd_engine_not_found"),
            )
            return

        editor_cmd = get_editor_cmd_path(engine)
        if not editor_cmd:
            MessageDialog.warning(
                self, tr("error"), tr("cmd_editor_not_found"),
            )
            return

        params = self._detail.get_all_params()

        # Build command preview
        cmd = build_command(editor_cmd, project, cmd_info.name, params)
        cmd_str = " ".join(cmd)

        result = MessageDialog.question(
            self,
            tr("cmd_run"),
            tr("cmd_confirm", name=cmd_info.name)
            + f"\n\n{cmd_str}",
            [tr("no"), tr("yes")],
        )
        if result != tr("yes"):
            return

        self._detail.show_console()
        self._detail.set_running(True, cmd_info.name)
        self.status_changed.emit(StatusKind.RUNNING, tr("cmd_in_progress"))

        self._exec_thread = QThread()
        self._exec_worker = _RunWorker(
            editor_cmd, project, cmd_info.name, params,
        )
        self._exec_worker.moveToThread(self._exec_thread)
        self._exec_thread.started.connect(self._exec_worker.run)
        self._exec_worker.finished.connect(
            self._on_exec_done, Qt.ConnectionType.QueuedConnection,
        )
        self._exec_worker.finished.connect(self._exec_thread.quit)
        self._exec_worker.log_message.connect(
            self._on_log_message, Qt.ConnectionType.QueuedConnection,
        )
        self._exec_thread.start()

    @Slot(object)
    def _on_log_message(self, msg) -> None:
        """Receive log message from run worker on the main thread."""
        self._detail.console.append_log(msg)

    def _on_cancel(self) -> None:
        """Cancel a running commandlet."""
        if self._exec_worker:
            self._exec_worker.cancel()

    @Slot(object)
    def _on_exec_done(self, result: RunResult) -> None:
        self._detail.set_running(False)
        if result.status == RunStatus.SUCCESS:
            self.status_changed.emit(StatusKind.SUCCESS, tr("success"))
            MessageDialog.information(
                self,
                tr("cmd_complete"),
                tr("cmd_successful", time=result.duration_seconds),
            )
        elif result.status == RunStatus.CANCELLED:
            self.status_changed.emit(StatusKind.IDLE, tr("cancelled"))
        else:
            self.status_changed.emit(StatusKind.FAILED, tr("failed"))
            MessageDialog.error(
                self,
                tr("cmd_failed_title"),
                tr("cmd_failed_msg", error=result.message),
            )

    # ------------------------------------------------------------------
    # Host interface
    # ------------------------------------------------------------------

    def get_settings_tabs(self) -> list:
        return []

    def show_settings(self) -> None:
        from framekit.dialogs import SettingsDialog
        SettingsDialog(self, extra_tabs=self.get_settings_tabs()).exec()

    def can_close(self) -> bool:
        if self._exec_thread and self._exec_thread.isRunning():
            result = MessageDialog.question(
                self,
                tr("cmd_in_progress"),
                tr("cmd_cancel_and_exit"),
                [tr("no"), tr("yes")],
            )
            if result != tr("yes"):
                return False
            if self._exec_worker:
                self._exec_worker.cancel()
        return True

    def cleanup(self) -> None:
        self._scan_gen += 1
        try:
            if self._exec_thread is not None and self._exec_thread.isRunning():
                if self._exec_worker:
                    self._exec_worker.cancel()
                self._exec_thread.quit()
                self._exec_thread.wait(3000)
        except RuntimeError:
            pass