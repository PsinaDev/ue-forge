# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for UE Forge (combined host)."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


project_root = Path(SPECPATH).parent
block_cipher = None

winpty_datas, winpty_binaries, winpty_hidden = collect_all("winpty")

# Private pages live in a git-ignored ue_forge/private/ package on the
# maintainer's machine. Pull in their hidden imports when present so this single
# spec builds with or without them; a public clone has no such package and
# builds the public tools only — out of the box, nothing to edit by hand.
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
try:
    from ue_forge.private import get_hidden_imports as _get_private_hidden
    _PRIVATE_HIDDEN = _get_private_hidden()
except Exception:
    _PRIVATE_HIDDEN = []


_FRAMEKIT_HIDDEN = [
    "framekit",
    "framekit.app",
    "framekit.config",
    "framekit.icons",
    "framekit.localization",
    "framekit.platform",
    "framekit.styles",
    "framekit.types",
    "framekit.dialogs",
    "framekit.dialogs.message_dialog",
    "framekit.dialogs.settings_dialog",
    "framekit.widgets",
    "framekit.widgets.console_widget",
    "framekit.widgets.path_input",
    "framekit.widgets.scrolling_label",
    "framekit.widgets.status_badge",
    "framekit.shell",
    "framekit.shell.host_window",
    "framekit.shell.page_protocol",
    "framekit.shell.single_page_shell",
]

_UE_FORGE_HIDDEN = [
    "ue_forge",
    "ue_forge.assets",
    "ue_forge.config",
    "ue_forge.platform",
    # plugin_builder
    "ue_forge.plugin_builder",
    "ue_forge.plugin_builder.strings",
    "ue_forge.plugin_builder.types",
    "ue_forge.plugin_builder.builder",
    "ue_forge.plugin_builder.engine_finder",
    "ue_forge.plugin_builder.page",
    "ue_forge.plugin_builder.info_card",
    "ue_forge.plugin_builder.advanced_options_dialog",
    "ue_forge.plugin_builder.command_dialog",
    "ue_forge.plugin_builder.engine_entry_dialog",
    "ue_forge.plugin_builder.engines_settings_tab",
    # renamer
    "ue_forge.renamer",
    "ue_forge.renamer.strings",
    "ue_forge.renamer.core",
    "ue_forge.renamer.page",
    # include_optimizer
    "ue_forge.include_optimizer",
    "ue_forge.include_optimizer.strings",
    "ue_forge.include_optimizer.core",
    "ue_forge.include_optimizer.page",
    # commandlet_runner
    "ue_forge.commandlet_runner",
    "ue_forge.commandlet_runner.strings",
    "ue_forge.commandlet_runner.core",
    "ue_forge.commandlet_runner.page",
]


a = Analysis(
    [str(project_root / "ue_forge" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=winpty_binaries,
    datas=[
        (str(project_root / "ue_forge" / "resources" / "icon.png"), "ue_forge/resources"),
        (str(project_root / "ue_forge" / "resources" / "icon.ico"), "ue_forge/resources"),
    ] + winpty_datas,
    hiddenimports=[
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtSvg",
        "pyside_frameless", "pyside_frameless.frameless_window", "pyside_frameless.drop_overlay",
        *_FRAMEKIT_HIDDEN,
        *_UE_FORGE_HIDDEN,
        *_PRIVATE_HIDDEN,
        "winpty", "winpty.ptyprocess", "winpty.winpty_wrapper",
    ] + winpty_hidden,
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL", "cv2"],
    win_no_prefer_redirects=False, win_private_assemblies=False,
    cipher=block_cipher, noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="UE Forge",
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=str(project_root / "ue_forge" / "resources" / "icon.ico"),
)
