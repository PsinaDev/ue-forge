"""
UE Forge-specific platform handlers.

Extends framekit's platform layer with Unreal Engine discovery,
UAT/editor binary naming, and process-tree termination that knows
about UBT / shader compiler workers.
"""

from __future__ import annotations

import os
import subprocess
from abc import abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from framekit.platform import (
    LinuxHandler,
    MacOSHandler,
    PlatformHandler,
    WindowsHandler,
    get_platform,
)


@runtime_checkable
class UEPlatformHandler(Protocol):
    """Structural interface for UE-specific platform helpers."""

    @abstractmethod
    def get_uat_script_name(self) -> str: ...

    @abstractmethod
    def get_editor_executable_name(self) -> str: ...

    @abstractmethod
    def get_binaries_subdir(self) -> str: ...

    @abstractmethod
    def get_registry_engine_paths(self) -> list[str]: ...

    @abstractmethod
    def get_standard_install_paths(self) -> list[Path]: ...


class UEWindowsHandler(WindowsHandler):
    """Windows handler with UE-specific extensions."""

    def get_uat_script_name(self) -> str:
        return "RunUAT.bat"

    def get_editor_executable_name(self) -> str:
        return "UnrealEditor.exe"

    def get_binaries_subdir(self) -> str:
        return "Win64"

    def kill_process_tree(self, pid: int) -> bool:
        ok = super().kill_process_tree(pid)
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW
            for proc_name in (
                "UnrealBuildTool.exe",
                "UBT.exe",
                "ShaderCompileWorker.exe",
            ):
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=creation_flags,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        return ok

    def get_registry_engine_paths(self) -> list[str]:
        """Get engine paths from the Windows registry."""
        paths: list[str] = []
        try:
            import winreg

            registry_keys = [
                r"SOFTWARE\EpicGames\Unreal Engine",
                r"SOFTWARE\EpicGames",
            ]
            for reg_path in registry_keys:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                        subkeys_count, _, _ = winreg.QueryInfoKey(key)
                        for i in range(subkeys_count):
                            subkey_name = winreg.EnumKey(key, i)
                            try:
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    install_path, _ = winreg.QueryValueEx(
                                        subkey, "InstalledDirectory"
                                    )
                                    if install_path and os.path.exists(install_path):
                                        paths.append(install_path)
                            except (FileNotFoundError, OSError):
                                continue
                except (FileNotFoundError, OSError):
                    continue
        except ImportError:
            pass
        return paths

    def get_standard_install_paths(self) -> list[Path]:
        """Get standard installation paths, scanning all available drives."""
        paths: list[Path] = [
            Path("C:/Program Files/Epic Games"),
            Path("C:/Epic Games"),
            Path.home() / "Epic Games",
        ]
        try:
            import string

            common_folders = ["Epic Games", "Engines", "UnrealEngine", "UE", "Unreal"]
            for letter in string.ascii_uppercase:
                drive = Path(f"{letter}:/")
                if drive.exists():
                    for folder in common_folders:
                        folder_path = drive / folder
                        if folder_path.exists() and folder_path.is_dir():
                            paths.append(folder_path)
                    program_files = drive / "Program Files" / "Epic Games"
                    if program_files.exists():
                        paths.append(program_files)
        except Exception:
            pass
        return paths


class UELinuxHandler(LinuxHandler):
    """Linux handler with UE-specific extensions."""

    def get_uat_script_name(self) -> str:
        return "RunUAT.sh"

    def get_editor_executable_name(self) -> str:
        return "UnrealEditor"

    def get_binaries_subdir(self) -> str:
        return "Linux"

    def get_registry_engine_paths(self) -> list[str]:
        return []

    def get_standard_install_paths(self) -> list[Path]:
        return [
            Path.home() / "UnrealEngine",
            Path("/opt/UnrealEngine"),
            Path.home() / ".local" / "share" / "Epic" / "UnrealEngine",
        ]


class UEMacOSHandler(MacOSHandler):
    """macOS handler with UE-specific extensions."""

    def get_uat_script_name(self) -> str:
        return "RunUAT.sh"

    def get_editor_executable_name(self) -> str:
        return "UnrealEditor"

    def get_binaries_subdir(self) -> str:
        return "Mac"

    def get_registry_engine_paths(self) -> list[str]:
        return []

    def get_standard_install_paths(self) -> list[Path]:
        return [
            Path("/Users/Shared/Epic Games"),
            Path.home() / "Epic Games",
            Path("/Applications/Epic Games"),
        ]


def ue_handler_for(app_slug: str) -> PlatformHandler:
    """Build the UE-flavoured handler for the current OS."""
    platform = get_platform()
    if platform == "windows":
        return UEWindowsHandler(app_slug)
    if platform == "macos":
        return UEMacOSHandler(app_slug)
    return UELinuxHandler(app_slug)


def ue_platform_handler() -> UEPlatformHandler:
    """
    Return the global platform handler, structurally typed as ``UEPlatformHandler``.

    Raises a ``TypeError`` if the installed handler does not implement the
    UE interface — this catches accidental use of the plain framekit handler.
    """
    from framekit.platform import platform_handler as _ph

    handler = _ph()
    if not isinstance(handler, UEPlatformHandler):
        raise TypeError(
            "installed platform handler does not implement UEPlatformHandler; "
            "install UEWindowsHandler / UELinuxHandler / UEMacOSHandler at startup"
        )
    return handler
