"""
Plugin Builder page for UE Forge.

Contains all plugin build UI and logic, extracted from the original MainWindow.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QFrame,
    QSplitter,
    QProgressBar,
    QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject

from ue_forge.shared.styles import COLORS, FONTS, RADIUS
from ue_forge.shared.icons import Icons
from ue_forge.shared.widgets import ConsoleWidget, PathInput, StatusBadge
from pyside_frameless import DropZoneWidget
from .info_card import InfoCard
from .advanced_options_dialog import AdvancedOptionsDialog
from .command_dialog import CommandDialog
from ue_forge.shared.dialogs import MessageDialog
from ue_forge.shared.types import LogLevel, LogMessage
from ue_forge.shared.localization import tr
from ue_forge.shared.config import get_config_manager
from .types import BuildConfig, BuildStatus, BuildResult, PluginInfo, EngineInfo
from .engine_finder import EngineFinder
from .builder import PluginBuilder


# ---------------------------------------------------------------------------
# Workers (moved from main_window.py without changes)
# ---------------------------------------------------------------------------

class EngineSearchWorker(QObject):
    """Worker for searching engines in background thread."""

    finished = Signal(dict)  # Dict[str, EngineInfo]
    log_message = Signal(object)  # LogMessage

    def __init__(self, engine_finder: EngineFinder, force_rescan: bool = False):
        super().__init__()
        self._finder = engine_finder
        self._force_rescan = force_rescan

    def run(self) -> None:
        """Execute engine search."""
        self._finder.set_log_callback(lambda msg: self.log_message.emit(msg))
        engines = self._finder.find_all_engines(force_rescan=self._force_rescan)
        self.finished.emit(engines)


class BuildWorker(QObject):
    """Worker for running build in background thread."""

    finished = Signal(object)  # BuildResult
    log_message = Signal(object)  # LogMessage
    progress = Signal(int)
    status_changed = Signal(object)  # BuildStatus

    def __init__(self, builder: PluginBuilder, config: BuildConfig):
        super().__init__()
        self._builder = builder
        self._config = config

    def run(self) -> None:
        """Execute build."""
        self._builder.set_log_callback(lambda msg: self.log_message.emit(msg))
        self._builder.set_progress_callback(lambda p: self.progress.emit(p))
        self._builder.set_status_callback(lambda s: self.status_changed.emit(s))

        result = self._builder.build_plugin(self._config, blocking=True)
        self.finished.emit(result)


class UATHelpWorker(QObject):
    """Worker for running UAT help command in background thread."""

    finished = Signal()
    output_line = Signal(str)
    error = Signal(str)

    def __init__(self, uat_path: str):
        super().__init__()
        self._uat_path = uat_path

    def run(self) -> None:
        """Execute UAT help command."""
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            result = subprocess.run(
                [self._uat_path, "BuildPlugin", "-help"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=creation_flags,
            )
            output = result.stdout + result.stderr
            for line in output.splitlines():
                if line.strip():
                    self.output_line.emit(line)
        except subprocess.TimeoutExpired:
            self.error.emit("Help command timed out")
        except Exception as e:
            self.error.emit(f"Error: {e}")

        self.finished.emit()


# ---------------------------------------------------------------------------
# PluginPanel (moved from main_window.py without changes)
# ---------------------------------------------------------------------------

class PluginPanel(DropZoneWidget):
    """Left panel with plugin configuration and drop zone support."""

    plugin_changed = Signal(str)
    refresh_requested = Signal()
    version_warning = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, valid_extensions=[".uplugin"], allow_directories=True)
        self._plugin_info: Optional[PluginInfo] = None
        self._setup_ui()
        overlay = self.setup_drop_overlay()
        overlay.configure(
            valid_pixmap=Icons.get_pixmap("UPLOAD", 48, "rgba(34, 211, 238, 1)"),
            invalid_pixmap=Icons.get_pixmap("X_CIRCLE", 48, "rgba(248, 113, 113, 1)"),
            invalid_text=tr("invalid_drop_file"),
        )
        self.set_drop_callback(self._on_plugin_dropped)

    def _setup_ui(self) -> None:
        """Set up the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)

        # ===== PLUGIN SECTION =====
        plugin_header = QHBoxLayout()
        plugin_header.setSpacing(8)

        plugin_icon = QLabel()
        plugin_icon.setPixmap(Icons.get_pixmap("PUZZLE", 20, COLORS['accent_primary']))
        plugin_icon.setFixedSize(20, 20)
        plugin_header.addWidget(plugin_icon)

        plugin_title = QLabel(tr("plugin"))
        plugin_title.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: {FONTS['size_xl']};
            font-weight: 600;
        """)
        plugin_header.addWidget(plugin_title)
        plugin_header.addStretch()

        content_layout.addLayout(plugin_header)

        # Plugin path input
        self._plugin_input = PathInput(
            label=tr("select_uplugin_file"),
            placeholder=tr("path_to_plugin_file"),
            hint=tr("drag_drop_hint"),
            icon_name="FILE_CODE",
            file_filter="Unreal Plugin (*.uplugin)",
        )
        self._plugin_input.path_changed.connect(self._on_plugin_path_changed)
        content_layout.addWidget(self._plugin_input)

        # Plugin info card
        self._info_card = InfoCard(title=tr("plugin_information"))
        content_layout.addWidget(self._info_card)

        # ===== TARGET ENGINE SECTION =====
        engine_card = QFrame()
        engine_card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(24, 24, 27, 0.3);
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']};
            }}
        """)
        engine_layout = QVBoxLayout(engine_card)
        engine_layout.setContentsMargins(16, 16, 16, 16)
        engine_layout.setSpacing(12)

        # Engine header
        engine_header = QHBoxLayout()
        engine_header.setSpacing(8)

        engine_icon = QLabel()
        engine_icon.setPixmap(Icons.get_pixmap("HARD_DRIVE", 16, COLORS['accent_primary']))
        engine_icon.setFixedSize(16, 16)
        engine_header.addWidget(engine_icon)

        engine_title = QLabel(tr("target_engine"))
        engine_title.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: {FONTS['size_sm']};
            font-weight: 500;
        """)
        engine_header.addWidget(engine_title)
        engine_header.addStretch()

        # Refresh button
        self._refresh_btn = QPushButton()
        self._refresh_btn.setIcon(Icons.get_icon("REFRESH_CW", 14, COLORS['text_muted']))
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setToolTip(tr("rescan_engines"))
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_tertiary']};
            }}
        """)
        self._refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        engine_header.addWidget(self._refresh_btn)

        engine_layout.addLayout(engine_header)

        # Engine selector row
        selector_row = QHBoxLayout()
        selector_row.setSpacing(12)

        target_label = QLabel(tr("build_for"))
        target_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        selector_row.addWidget(target_label)

        self._engine_combo = QComboBox()
        self._engine_combo.setMinimumWidth(160)
        self._engine_combo.setPlaceholderText(tr("select_version"))
        self._engine_combo.currentIndexChanged.connect(self._check_version_match)
        selector_row.addWidget(self._engine_combo, 1)

        engine_layout.addLayout(selector_row)

        # Version warning label (hidden by default)
        self._version_warning_label = QLabel()
        self._version_warning_label.setStyleSheet(f"""
            color: {COLORS['error']};
            font-size: {FONTS['size_sm']};
            font-weight: 500;
            background: transparent;
            padding: 4px 0px;
        """)
        self._version_warning_label.setVisible(False)
        engine_layout.addWidget(self._version_warning_label)

        content_layout.addWidget(engine_card)

        # ===== OUTPUT DIRECTORY SECTION =====
        output_label = QLabel(tr("output_directory"))
        output_label.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-size: {FONTS['size_sm']};
            font-weight: 500;
        """)
        content_layout.addWidget(output_label)

        # Radio buttons for output selection
        self._radio_group = QButtonGroup(self)

        self._parent_radio = QRadioButton(tr("to_parent_directory"))
        self._parent_radio.setChecked(True)
        self._parent_radio.toggled.connect(self._on_radio_toggled)
        self._radio_group.addButton(self._parent_radio, 0)
        content_layout.addWidget(self._parent_radio)

        self._custom_radio = QRadioButton(tr("select_another_directory"))
        self._custom_radio.toggled.connect(self._on_radio_toggled)
        self._radio_group.addButton(self._custom_radio, 1)
        content_layout.addWidget(self._custom_radio)

        # Custom output path (hidden by default)
        self._custom_output = PathInput(
            placeholder=tr("output_path"),
            icon_name="FOLDER_OPEN",
            directory_mode=True,
        )
        self._custom_output.setVisible(False)
        content_layout.addWidget(self._custom_output)

        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _on_radio_toggled(self, checked: bool) -> None:
        """Handle radio button toggle."""
        self._custom_output.setVisible(self._custom_radio.isChecked())

    def _on_plugin_dropped(self, path: str) -> None:
        """Handle plugin dropped via drag & drop."""
        self._plugin_input.set_path(path)

    def _on_plugin_path_changed(self, path: str) -> None:
        """Handle plugin path change."""
        self.plugin_changed.emit(path)
        self._update_plugin_info(path)
        self._check_version_match()

    def _check_version_match(self) -> None:
        """Check if target version matches plugin version and show warning."""
        if not self._plugin_info or not self._plugin_info.engine_version:
            self._version_warning_label.setVisible(False)
            return

        target_version = self._engine_combo.currentData()
        if not target_version:
            self._version_warning_label.setVisible(False)
            return

        # Normalize versions
        def normalize_version(v: str) -> str:
            parts = v.replace("UE ", "").split(".")
            if len(parts) >= 2:
                return f"{parts[0]}.{parts[1]}"
            return parts[0] if parts else ""

        plugin_normalized = normalize_version(self._plugin_info.engine_version)
        target_normalized = normalize_version(target_version)

        if plugin_normalized == target_normalized:
            self._version_warning_label.setText(tr("version_warning"))
            self._version_warning_label.setVisible(True)
            self.version_warning.emit(
                f"Target version ({target_version}) matches plugin's engine version ({self._plugin_info.engine_version})"
            )
        else:
            self._version_warning_label.setVisible(False)

    def _update_plugin_info(self, path: str) -> None:
        """Update plugin info card."""
        if not path:
            self._plugin_info = None
            self._info_card.clear_items()
            return

        plugin_path = Path(path)
        if not plugin_path.exists() or plugin_path.suffix != ".uplugin":
            self._plugin_info = None
            self._info_card.clear_items()
            return

        self._plugin_info = PluginBuilder.extract_plugin_info(plugin_path)

        if self._plugin_info:
            self._info_card.set_plugin_info(self._plugin_info)
        else:
            self._info_card.clear_items()

    def set_engines(self, engines: Dict[str, EngineInfo]) -> None:
        """Set available engines."""
        current = self._engine_combo.currentData()
        self._engine_combo.clear()

        for version in sorted(engines.keys(), reverse=True):
            self._engine_combo.addItem(f"UE {version}", version)

        if current:
            idx = self._engine_combo.findData(current)
            if idx >= 0:
                self._engine_combo.setCurrentIndex(idx)

        self._check_version_match()

    def get_plugin_path(self) -> str:
        return self._plugin_input.path()

    def get_selected_engine(self) -> Optional[str]:
        return self._engine_combo.currentData()

    def get_output_path(self) -> Optional[str]:
        plugin_path = self.get_plugin_path()
        if not plugin_path:
            return None

        if self._parent_radio.isChecked():
            # Build to PARENT directory (one level up from plugin folder)
            plugin_dir = Path(plugin_path).parent  # Folder containing .uplugin
            parent_dir = plugin_dir.parent  # One level up
            plugin_name = plugin_dir.name  # Use folder name, not file name

            # Use engine version as suffix (e.g., _5.4)
            engine_version = self.get_selected_engine()
            if engine_version:
                suffix = f"_{engine_version}"
            else:
                suffix = "_Built"

            return str(parent_dir / f"{plugin_name}{suffix}")
        else:
            return self._custom_output.path() or None

    @property
    def plugin_info(self) -> Optional[PluginInfo]:
        return self._plugin_info


# ---------------------------------------------------------------------------
# PluginBuilderPage
# ---------------------------------------------------------------------------

class PluginBuilderPage(QWidget):
    """
    Self-contained page for building Unreal Engine plugins.

    Communicates with the host window via:
      - status_changed(badge_status: str, text: str)  -> update host status badge
    """

    PAGE_ID = "plugin_builder"
    PAGE_ICON = "HAMMER"

    # Signal to host window for status badge updates
    status_changed = Signal(str, str)

    # Left panel width - FIXED
    LEFT_PANEL_WIDTH = 480

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Core components
        self._config = get_config_manager()
        self._engine_finder = EngineFinder()
        self._plugin_builder = PluginBuilder()
        self._engines: Dict[str, EngineInfo] = {}

        # Build state
        self._build_thread: Optional[QThread] = None
        self._build_worker: Optional[BuildWorker] = None
        self._engine_thread: Optional[QThread] = None
        self._engine_worker: Optional[EngineSearchWorker] = None
        self._help_thread: Optional[QThread] = None
        self._help_worker: Optional[UATHelpWorker] = None

        # Build options (from Advanced Options dialog)
        self._build_options: Dict[str, Any] = {}

        # Status reset timer (resets status badge after build completion)
        self._status_reset_timer = QTimer()
        self._status_reset_timer.setSingleShot(True)
        self._status_reset_timer.timeout.connect(self._reset_status)

        self._setup_ui()
        self._connect_signals()
        self._load_config()

        QTimer.singleShot(100, self._search_engines)

    @staticmethod
    def page_title() -> str:
        return tr("plugin_builder")

    def _setup_ui(self) -> None:
        """Set up the page layout with splitter."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main content with splitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['border_default']};
            }}
        """)

        # Left panel - Plugin configuration (FIXED width)
        self._plugin_panel = PluginPanel()
        self._plugin_panel.setFixedWidth(self.LEFT_PANEL_WIDTH)
        self._splitter.addWidget(self._plugin_panel)

        # Right panel - Console and controls (flexible width)
        right_panel = self._create_right_panel()
        right_panel.setMinimumWidth(400)
        self._splitter.addWidget(right_panel)

        # Set initial sizes
        self._splitter.setSizes([self.LEFT_PANEL_WIDTH, 720])

        # Left panel fixed, console stretches
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)

        # Disable splitter handle (no manual resize)
        self._splitter.handle(1).setEnabled(False)
        self._splitter.handle(1).setCursor(Qt.CursorShape.ArrowCursor)

        layout.addWidget(self._splitter, 1)

    def _create_right_panel(self) -> QWidget:
        """Create right panel with console and controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Console
        self._console = ConsoleWidget()
        layout.addWidget(self._console, 1)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(3)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        # Control bar
        controls = self._create_controls()
        layout.addWidget(controls)

        return panel

    def _create_controls(self) -> QWidget:
        """Create control bar."""
        controls = QFrame()
        controls.setObjectName("builderControls")
        controls.setFixedHeight(64)
        controls.setStyleSheet(f"""
            QFrame#builderControls {{
                background: rgba(24, 24, 27, 0.5);
                border: none;
                border-top: 1px solid {COLORS['border_default']};
            }}
        """)

        layout = QHBoxLayout(controls)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(12)

        # Advanced options button
        self._advanced_btn = QPushButton(f"  {tr('advanced_options')}")
        self._advanced_btn.setIcon(Icons.get_icon("SETTINGS", 14, COLORS["text_dim"]))
        self._advanced_btn.setCursor(Qt.PointingHandCursor)
        self._advanced_btn.clicked.connect(self._show_advanced_options)
        layout.addWidget(self._advanced_btn)

        # Show command button
        self._show_cmd_btn = QPushButton(f"  {tr('show_command')}")
        self._show_cmd_btn.setIcon(Icons.get_icon("TERMINAL", 14, COLORS["text_dim"]))
        self._show_cmd_btn.setCursor(Qt.PointingHandCursor)
        self._show_cmd_btn.clicked.connect(self._show_command)
        layout.addWidget(self._show_cmd_btn)

        # UAT Help button
        self._help_btn = QPushButton(f"  {tr('uat_help')}")
        self._help_btn.setIcon(Icons.get_icon("HASH", 14, COLORS["text_dim"]))
        self._help_btn.setCursor(Qt.PointingHandCursor)
        self._help_btn.clicked.connect(self._show_uat_help)
        layout.addWidget(self._help_btn)

        layout.addStretch()

        # Cancel button (hidden by default)
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
        self._cancel_btn.clicked.connect(self._cancel_build)
        layout.addWidget(self._cancel_btn)

        # Build button
        self._build_btn = QPushButton(f"  {tr('build_plugin')}")
        self._build_btn.setIcon(Icons.get_icon("PLAY", 16, "#ffffff"))
        self._build_btn.setProperty("class", "primary")
        self._build_btn.setFixedWidth(180)
        self._build_btn.setFixedHeight(40)
        self._build_btn.setCursor(Qt.PointingHandCursor)
        self._build_btn.clicked.connect(self._start_build)
        layout.addWidget(self._build_btn)

        return controls

    # ------------------------------------------------------------------
    # Signal connections
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._plugin_panel.plugin_changed.connect(self._on_plugin_changed)
        self._plugin_panel.refresh_requested.connect(
            lambda: self._search_engines(force=True)
        )
        self._plugin_panel.version_warning.connect(
            lambda msg: self._console.append(msg, LogLevel.WARNING)
        )

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load saved configuration."""
        config = self._config.load_config()
        self._build_options = config.build_options.copy() if config.build_options else {}

    def _save_config(self) -> None:
        """Save configuration."""
        plugin_path = self._plugin_panel.get_plugin_path()
        output_path = self._plugin_panel.get_output_path()

        self._config.update_config(
            last_plugin_path=plugin_path,
            last_output_path=output_path or "",
            build_options=self._build_options,
        )

    # ------------------------------------------------------------------
    # Engine search
    # ------------------------------------------------------------------

    def _search_engines(self, force: bool = False) -> None:
        """Search for engines in background."""
        self._console.append(tr("searching_engines"), LogLevel.INFO)

        self._engine_thread = QThread()
        self._engine_worker = EngineSearchWorker(self._engine_finder, force_rescan=force)
        self._engine_worker.moveToThread(self._engine_thread)

        self._engine_thread.started.connect(self._engine_worker.run)
        self._engine_worker.finished.connect(
            self._on_engines_found, Qt.ConnectionType.QueuedConnection
        )
        self._engine_worker.finished.connect(self._engine_thread.quit)
        self._engine_worker.log_message.connect(
            self._on_log_message, Qt.ConnectionType.QueuedConnection
        )

        self._engine_thread.finished.connect(self._engine_worker.deleteLater)
        self._engine_thread.finished.connect(self._engine_thread.deleteLater)

        self._engine_thread.start()

    @Slot(dict)
    def _on_engines_found(self, engines: Dict[str, EngineInfo]) -> None:
        """Handle engine search completion."""
        self._engines = engines
        self._plugin_panel.set_engines(engines)

        if engines:
            self._console.append(
                tr("found_n_engines", count=len(engines)), LogLevel.SUCCESS
            )
        else:
            self._console.append(
                tr("no_engines_add_manually"), LogLevel.WARNING
            )

    # ------------------------------------------------------------------
    # Plugin change handling
    # ------------------------------------------------------------------

    def _on_plugin_changed(self, path: str) -> None:
        """Handle plugin path change."""
        self._status_reset_timer.stop()
        self._reset_status()

        if path and Path(path).exists():
            self._console.append(tr("plugin_selected", path=path), LogLevel.INFO)

    # ------------------------------------------------------------------
    # Build validation and execution
    # ------------------------------------------------------------------

    def _validate_build(self) -> bool:
        """Validate build configuration."""
        plugin_path = self._plugin_panel.get_plugin_path()
        if not plugin_path:
            MessageDialog.warning(self, tr("validation_error"), tr("select_plugin_file"))
            return False

        if not Path(plugin_path).exists():
            MessageDialog.warning(self, tr("validation_error"), tr("plugin_not_found"))
            return False

        engine_version = self._plugin_panel.get_selected_engine()
        if not engine_version:
            MessageDialog.warning(self, tr("validation_error"), tr("select_target_engine"))
            return False

        if engine_version not in self._engines:
            MessageDialog.warning(self, tr("validation_error"), tr("engine_not_found"))
            return False

        output_path = self._plugin_panel.get_output_path()
        if not output_path:
            MessageDialog.warning(self, tr("validation_error"), tr("specify_output_dir"))
            return False

        return True

    def _get_build_config(self) -> Optional[BuildConfig]:
        """Create build configuration from current settings."""
        if not self._validate_build():
            return None

        plugin_path = Path(self._plugin_panel.get_plugin_path())
        output_path = Path(self._plugin_panel.get_output_path())
        engine_version = self._plugin_panel.get_selected_engine()
        engine_info = self._engines[engine_version]

        # Parse target platforms
        platforms_str = self._build_options.get("TargetPlatforms", "Win64")
        target_platforms = platforms_str.split("+") if platforms_str else ["Win64"]

        # Extract extra params (non-standard options)
        standard_keys = {"TargetPlatforms", "NoHostPlatform", "StrictIncludes", "Unversioned", "ExtraParams"}
        extra_params = {k: v for k, v in self._build_options.items() if k not in standard_keys}

        # Add raw extra params text if present
        extra_params_text = self._build_options.get("ExtraParams", "")
        if extra_params_text:
            from .builder import parse_extra_params
            extra_params.update(parse_extra_params(extra_params_text))

        return BuildConfig(
            plugin_path=plugin_path,
            output_path=output_path,
            engine_path=engine_info.path,
            target_platforms=target_platforms,
            no_host_platform=self._build_options.get("NoHostPlatform", False),
            strict_includes=self._build_options.get("StrictIncludes", False),
            unversioned=self._build_options.get("Unversioned", False),
            extra_params=extra_params,
        )

    def _start_build(self) -> None:
        """Start plugin build."""
        config = self._get_build_config()
        if not config:
            return

        self._set_build_running(True)
        self._console.clear()
        self._progress_bar.setValue(0)

        self._build_thread = QThread()
        self._build_worker = BuildWorker(self._plugin_builder, config)
        self._build_worker.moveToThread(self._build_thread)

        self._build_thread.started.connect(self._build_worker.run)
        self._build_worker.finished.connect(
            self._on_build_finished, Qt.ConnectionType.QueuedConnection
        )
        self._build_worker.finished.connect(self._build_thread.quit)
        self._build_worker.log_message.connect(
            self._on_log_message, Qt.ConnectionType.QueuedConnection
        )
        self._build_worker.progress.connect(
            self._progress_bar.setValue, Qt.ConnectionType.QueuedConnection
        )
        self._build_worker.status_changed.connect(
            self._on_build_status_changed, Qt.ConnectionType.QueuedConnection
        )

        self._build_thread.finished.connect(self._build_worker.deleteLater)
        self._build_thread.finished.connect(self._build_thread.deleteLater)

        self._build_thread.start()

    @Slot(object)
    def _on_log_message(self, msg: LogMessage) -> None:
        """Handle log message from worker thread."""
        self._console.append_log(msg)

    def _cancel_build(self) -> None:
        """Cancel ongoing build."""
        if self._plugin_builder.is_running:
            self._plugin_builder.cancel_build()

    @Slot(object)
    def _on_build_finished(self, result: BuildResult) -> None:
        """Handle build completion."""
        self._set_build_running(False)

        # Stop any pending reset timer
        self._status_reset_timer.stop()

        if result.status == BuildStatus.SUCCESS:
            self.status_changed.emit("success", tr("success"))
            self._progress_bar.setValue(100)

            MessageDialog.information(
                self,
                tr("build_complete"),
                tr("build_successful", path=str(result.output_path))
            )
            self._status_reset_timer.start(10000)
        elif result.status == BuildStatus.CANCELLED:
            self.status_changed.emit("warning", tr("cancelled"))
            self._progress_bar.setValue(0)
            self._status_reset_timer.start(5000)
        else:
            self.status_changed.emit("failed", tr("failed"))
            self._progress_bar.setValue(0)

            error_summary = "\n".join(result.errors[:5]) if result.errors else result.message
            MessageDialog.error(
                self,
                tr("build_failed"),
                tr("build_failed_msg", error=error_summary)
            )
            self._status_reset_timer.start(10000)

    @Slot(object)
    def _on_build_status_changed(self, status: BuildStatus) -> None:
        """Handle build status change."""
        status_map = {
            BuildStatus.IDLE: ("idle", tr("ready")),
            BuildStatus.RUNNING: ("running", tr("building")),
            BuildStatus.SUCCESS: ("success", tr("success")),
            BuildStatus.FAILED: ("failed", tr("failed")),
            BuildStatus.CANCELLED: ("warning", tr("cancelled")),
        }

        badge_status, text = status_map.get(status, ("idle", tr("ready")))
        self.status_changed.emit(badge_status, text)

    def _set_build_running(self, running: bool) -> None:
        """Update UI for build running state."""
        self._build_btn.setEnabled(not running)
        self._cancel_btn.setVisible(running)
        self._advanced_btn.setEnabled(not running)
        self._show_cmd_btn.setEnabled(not running)
        self._help_btn.setEnabled(not running)

        if running:
            self._status_reset_timer.stop()
            self.status_changed.emit("running", tr("building"))
            self._progress_bar.setValue(0)

    @Slot()
    def _reset_status(self) -> None:
        """Reset status badge and progress bar to idle state."""
        if not self._plugin_builder.is_running:
            self.status_changed.emit("idle", tr("ready"))
            self._progress_bar.setValue(0)

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _show_command(self) -> None:
        """Show the build command in a dialog."""
        config = self._get_build_config()
        if not config:
            return

        command = self._plugin_builder.get_command_string(config)

        if command:
            dialog = CommandDialog(self, command=command)
            dialog.exec()
        else:
            MessageDialog.warning(
                self,
                tr("error"),
                tr("generate_command_error")
            )

    def _show_uat_help(self) -> None:
        """Show UAT BuildPlugin help in console."""
        engine_version = self._plugin_panel.get_selected_engine()
        if not engine_version or engine_version not in self._engines:
            MessageDialog.warning(
                self,
                tr("error"),
                tr("select_target_engine")
            )
            return

        engine_info = self._engines[engine_version]
        uat_path = self._plugin_builder.get_uat_path(engine_info.path)

        if not uat_path:
            MessageDialog.warning(
                self,
                tr("error"),
                tr("engine_not_found")
            )
            return

        self._console.clear()
        self._console.append(f"Running: {uat_path} BuildPlugin -help", LogLevel.INFO)
        self._console.append("=" * 60, LogLevel.INFO)

        # Run UAT help in background thread
        self._help_thread = QThread()
        self._help_worker = UATHelpWorker(str(uat_path))
        self._help_worker.moveToThread(self._help_thread)

        self._help_thread.started.connect(self._help_worker.run)
        self._help_worker.output_line.connect(
            self._console.append_raw, Qt.ConnectionType.QueuedConnection
        )
        self._help_worker.error.connect(
            lambda msg: self._console.append(msg, LogLevel.WARNING),
            Qt.ConnectionType.QueuedConnection
        )
        self._help_worker.finished.connect(self._help_thread.quit)
        self._help_thread.finished.connect(self._help_worker.deleteLater)
        self._help_thread.finished.connect(self._help_thread.deleteLater)

        self._help_thread.start()

    def _show_advanced_options(self) -> None:
        """Show advanced options dialog."""
        dialog = AdvancedOptionsDialog(self)
        dialog.set_options(self._build_options)

        if dialog.exec():
            self._build_options = dialog.get_options()
            self._save_config()
            self._console.append(tr("applied_options", options=str(self._build_options)), LogLevel.INFO)

    # ------------------------------------------------------------------
    # Host interface
    # ------------------------------------------------------------------

    def get_settings_tabs(self):
        """Return settings tabs contributed by this page."""
        from .engines_settings_tab import EnginesSettingsTab
        tab = EnginesSettingsTab(
            engine_finder=self._engine_finder,
            existing_engines={v: str(info.path) for v, info in self._engines.items()},
        )
        tab.engines_changed.connect(self._on_engines_settings_changed)
        return [tab]

    def _on_engines_settings_changed(self, engines_dict):
        """Handle engines changed from settings tab."""
        self._config.save_engines(engines_dict)
        self._search_engines()

    def show_settings(self) -> None:
        """Show settings dialog (called by host window)."""
        from ue_forge.shared.dialogs import SettingsDialog
        dlg = SettingsDialog(self, extra_tabs=self.get_settings_tabs())
        dlg.exec()

    def can_close(self) -> bool:
        """Check if the page can be closed (no active build)."""
        if self._plugin_builder.is_running:
            result = MessageDialog.question(
                self,
                tr("build_in_progress"),
                tr("cancel_and_exit"),
                [tr("no"), tr("yes")]
            )
            if result != tr("yes"):
                return False
            self._plugin_builder.cancel_build()
        return True

    def cleanup(self) -> None:
        """Cleanup threads and save config."""
        self._save_config()

        for thread in [self._build_thread, self._engine_thread, self._help_thread]:
            try:
                if thread is not None and thread.isRunning():
                    thread.quit()
                    thread.wait(3000)
            except RuntimeError:
                pass
