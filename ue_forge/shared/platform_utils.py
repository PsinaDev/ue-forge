"""
Platform-specific utilities for UE Forge.
Provides abstractions for Windows, Linux, and macOS.
"""
import os
import sys
import signal
import subprocess
from pathlib import Path
from typing import Optional, List, Dict
from abc import ABC, abstractmethod


def get_platform() -> str:
    """Get current platform identifier."""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    else:
        return "linux"


class PlatformHandler(ABC):
    """Abstract base class for platform-specific operations."""

    @abstractmethod
    def get_uat_script_name(self) -> str:
        """Get the name of the UAT script for this platform."""
        pass

    @abstractmethod
    def get_editor_executable_name(self) -> str:
        """Get the name of the editor executable for this platform."""
        pass

    @abstractmethod
    def get_binaries_subdir(self) -> str:
        """Get the binaries subdirectory for this platform."""
        pass

    @abstractmethod
    def kill_process_tree(self, pid: int) -> bool:
        """Kill a process and all its children."""
        pass

    @abstractmethod
    def get_registry_engine_paths(self) -> List[str]:
        """Get engine paths from system registry/configuration."""
        pass

    @abstractmethod
    def get_standard_install_paths(self) -> List[Path]:
        """Get standard installation paths for this platform."""
        pass

    @abstractmethod
    def get_config_dir(self) -> Path:
        """Get the configuration directory for this platform."""
        pass


class WindowsHandler(PlatformHandler):
    """Windows-specific platform handler."""

    def get_uat_script_name(self) -> str:
        return "RunUAT.bat"

    def get_editor_executable_name(self) -> str:
        return "UnrealEditor.exe"

    def get_binaries_subdir(self) -> str:
        return "Win64"

    def kill_process_tree(self, pid: int) -> bool:
        """Kill process tree on Windows using taskkill."""
        try:
            # Hide console window
            creation_flags = subprocess.CREATE_NO_WINDOW
            
            # Kill main process and all children
            result = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid), "/T"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=creation_flags,
            )
            
            # Also try to kill common UE build processes
            build_processes = ["UnrealBuildTool.exe", "UBT.exe", "ShaderCompileWorker.exe"]
            for proc_name in build_processes:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=creation_flags,
                )
            
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def get_registry_engine_paths(self) -> List[str]:
        """Get engine paths from Windows registry."""
        paths = []
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
                                    install_path, _ = winreg.QueryValueEx(subkey, "InstalledDirectory")
                                    if install_path and os.path.exists(install_path):
                                        paths.append(install_path)
                            except (FileNotFoundError, OSError):
                                continue
                except (FileNotFoundError, OSError):
                    continue
        except ImportError:
            pass
        
        return paths

    def get_standard_install_paths(self) -> List[Path]:
        """Get standard installation paths including all available drives."""
        paths = [
            Path("C:/Program Files/Epic Games"),
            Path("C:/Epic Games"),
            Path.home() / "Epic Games",
        ]
        
        # Scan all available drives for common UE folder names
        try:
            import string
            common_folders = ["Epic Games", "Engines", "UnrealEngine", "UE", "Unreal"]
            
            for letter in string.ascii_uppercase:
                drive = Path(f"{letter}:/")
                if drive.exists():
                    # Add drive root common folders
                    for folder in common_folders:
                        folder_path = drive / folder
                        if folder_path.exists() and folder_path.is_dir():
                            paths.append(folder_path)
                    
                    # Also check Program Files on other drives
                    program_files = drive / "Program Files" / "Epic Games"
                    if program_files.exists():
                        paths.append(program_files)
        except Exception:
            pass
        
        return paths

    def get_config_dir(self) -> Path:
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            return Path(local_appdata) / "UETools"
        return Path.home() / "AppData" / "Local" / "UETools"


class LinuxHandler(PlatformHandler):
    """Linux-specific platform handler."""

    def get_uat_script_name(self) -> str:
        return "RunUAT.sh"

    def get_editor_executable_name(self) -> str:
        return "UnrealEditor"

    def get_binaries_subdir(self) -> str:
        return "Linux"

    def kill_process_tree(self, pid: int) -> bool:
        """Kill process tree on Linux using process groups."""
        try:
            # Try to kill the process group
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            try:
                # Fallback: kill just the process
                os.kill(pid, signal.SIGKILL)
                return True
            except (ProcessLookupError, PermissionError, OSError):
                return False

    def get_registry_engine_paths(self) -> List[str]:
        """Linux doesn't have a registry, return empty list."""
        return []

    def get_standard_install_paths(self) -> List[Path]:
        return [
            Path.home() / "UnrealEngine",
            Path("/opt/UnrealEngine"),
            Path.home() / ".local" / "share" / "Epic" / "UnrealEngine",
        ]

    def get_config_dir(self) -> Path:
        xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg_config:
            return Path(xdg_config) / "ue-forge"
        return Path.home() / ".config" / "ue-forge"


class MacOSHandler(PlatformHandler):
    """macOS-specific platform handler."""

    def get_uat_script_name(self) -> str:
        return "RunUAT.sh"

    def get_editor_executable_name(self) -> str:
        return "UnrealEditor"

    def get_binaries_subdir(self) -> str:
        return "Mac"

    def kill_process_tree(self, pid: int) -> bool:
        """Kill process tree on macOS."""
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            try:
                os.kill(pid, signal.SIGKILL)
                return True
            except (ProcessLookupError, PermissionError, OSError):
                return False

    def get_registry_engine_paths(self) -> List[str]:
        """macOS doesn't have a registry, return empty list."""
        return []

    def get_standard_install_paths(self) -> List[Path]:
        return [
            Path("/Users/Shared/Epic Games"),
            Path.home() / "Epic Games",
            Path("/Applications/Epic Games"),
        ]

    def get_config_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / "UETools"


def get_platform_handler() -> PlatformHandler:
    """Get the appropriate platform handler for the current OS."""
    platform = get_platform()
    if platform == "windows":
        return WindowsHandler()
    elif platform == "macos":
        return MacOSHandler()
    else:
        return LinuxHandler()


# Global instance for convenience
_handler: Optional[PlatformHandler] = None


def platform_handler() -> PlatformHandler:
    """Get the global platform handler instance."""
    global _handler
    if _handler is None:
        _handler = get_platform_handler()
    return _handler
