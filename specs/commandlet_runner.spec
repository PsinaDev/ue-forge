# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the UE Commandlet Runner (standalone)."""

from pathlib import Path


project_root = Path(SPECPATH).parent
block_cipher = None


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

_UE_FORGE_CORE_HIDDEN = [
    "ue_forge",
    "ue_forge.assets",
    "ue_forge.config",
    "ue_forge.platform",
]

_COMMANDLET_RUNNER_HIDDEN = [
    "ue_forge.commandlet_runner",
    "ue_forge.commandlet_runner.strings",
    "ue_forge.commandlet_runner.core",
    "ue_forge.commandlet_runner.page",
]


a = Analysis(
    [str(project_root / "ue_forge" / "commandlet_runner" / "__main__.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "ue_forge" / "resources" / "icon.png"), "ue_forge/resources"),
        (str(project_root / "ue_forge" / "resources" / "icon.ico"), "ue_forge/resources"),
    ],
    hiddenimports=[
        "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtSvg",
        "pyside_frameless", "pyside_frameless.frameless_window", "pyside_frameless.drop_overlay",
        *_FRAMEKIT_HIDDEN,
        *_UE_FORGE_CORE_HIDDEN,
        *_COMMANDLET_RUNNER_HIDDEN,
    ],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL", "cv2"],
    win_no_prefer_redirects=False, win_private_assemblies=False,
    cipher=block_cipher, noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="UE Commandlet Runner",
    debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=str(project_root / "ue_forge" / "resources" / "icon.ico"),
)
