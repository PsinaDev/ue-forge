"""
Unreal Engine discovery module.
Finds installed UE instances without Qt dependencies.
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Callable

from .types import EngineInfo
from ue_forge.shared.types import LogLevel, LogMessage
from ue_forge.shared.platform_utils import platform_handler
from ue_forge.shared.config import get_config_manager


LogCallback = Callable[[LogMessage], None]


class EngineFinder:
    """
    Discovers installed Unreal Engine instances.
    
    Uses callback-based logging for UI-agnostic operation.
    Can be used both in GUI and headless environments.
    """

    POSSIBLE_ENGINE_NAMES = ["Unreal", "UE_", "UE5", "UE4"]

    def __init__(
        self,
        log_callback: Optional[LogCallback] = None,
        config_manager=None,
    ):
        self._log_callback = log_callback
        self._config = config_manager or get_config_manager()
        self._platform = platform_handler()
        self._found_engines: Dict[str, EngineInfo] = {}

    def set_log_callback(self, callback: LogCallback) -> None:
        """Set the logging callback."""
        self._log_callback = callback

    def _log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """Log a message through the callback if set."""
        if self._log_callback:
            self._log_callback(LogMessage(text=message, level=level))

    def is_valid_engine_path(self, engine_path: Path) -> bool:
        """
        Check if a path contains a valid Unreal Engine installation.
        
        Args:
            engine_path: Path to check
            
        Returns:
            True if valid UE installation, False otherwise
        """
        if not engine_path.exists():
            return False

        # Check for UAT script
        uat_script = self._platform.get_uat_script_name()
        uat_path = engine_path / "Engine" / "Build" / "BatchFiles" / uat_script
        if not uat_path.exists():
            return False

        # Check for editor executable
        binaries_dir = self._platform.get_binaries_subdir()
        
        # UE5 editor
        ue5_editor = engine_path / "Engine" / "Binaries" / binaries_dir / self._platform.get_editor_executable_name()
        # UE4 editor (different name on Windows)
        ue4_editor_name = "UE4Editor.exe" if binaries_dir == "Win64" else "UE4Editor"
        ue4_editor = engine_path / "Engine" / "Binaries" / binaries_dir / ue4_editor_name
        
        has_editor = ue5_editor.exists() or ue4_editor.exists()
        if not has_editor:
            return False

        # Check for required directories
        required_dirs = [
            engine_path / "Engine" / "Content",
            engine_path / "Engine" / "Plugins",
        ]
        
        return all(d.is_dir() for d in required_dirs)

    def extract_version(self, engine_path: Path) -> Optional[str]:
        """
        Extract UE version from engine installation.
        
        Tries multiple methods:
        1. Folder name pattern (e.g., UE_5.4)
        2. Build.version file
        
        Args:
            engine_path: Path to UE installation
            
        Returns:
            Version string (e.g., "5.4") or None
        """
        # Normalize path - ensure it points to UE root
        if (engine_path / "Engine").exists():
            pass
        elif engine_path.name == "Engine":
            engine_path = engine_path.parent

        # Try folder name pattern
        folder_name = engine_path.name
        version_match = re.search(r"UE_?(\d+\.\d+)", folder_name)
        if version_match:
            return version_match.group(1)

        # Try Build.version file
        version_file = engine_path / "Engine" / "Build" / "Build.version"
        if version_file.exists():
            try:
                with open(version_file, "r", encoding="utf-8") as f:
                    version_data = json.load(f)
                major = version_data.get("MajorVersion", 0)
                minor = version_data.get("MinorVersion", 0)
                return f"{major}.{minor}"
            except (json.JSONDecodeError, IOError, KeyError):
                pass

        return None

    def find_in_registry(self) -> List[Path]:
        """Find engine paths from system registry (Windows only)."""
        self._log("Searching in system registry...")
        paths = []
        
        registry_paths = self._platform.get_registry_engine_paths()
        for path_str in registry_paths:
            path = Path(path_str)
            if self.is_valid_engine_path(path):
                self._log(f"Found engine in registry: {path}", LogLevel.SUCCESS)
                paths.append(path)
        
        if not paths:
            self._log("No engines found in registry")
        
        return paths

    def find_in_environment(self) -> List[Path]:
        """Find engine paths from environment variables."""
        self._log("Checking environment variables...")
        paths = []
        
        for var_value in os.environ.values():
            if any(name in var_value for name in self.POSSIBLE_ENGINE_NAMES):
                path = Path(var_value)
                if path.exists() and self.is_valid_engine_path(path):
                    self._log(f"Found engine in environment: {path}", LogLevel.SUCCESS)
                    paths.append(path)
        
        if not paths:
            self._log("No engines found in environment variables")
        
        return paths

    def find_in_standard_paths(self) -> List[Path]:
        """Find engine installations in standard locations."""
        self._log("Searching standard installation paths...")
        paths = []
        
        for base_path in self._platform.get_standard_install_paths():
            if not base_path.exists():
                continue
            
            try:
                for subdir in base_path.iterdir():
                    if subdir.is_dir() and self.is_valid_engine_path(subdir):
                        self._log(f"Found engine: {subdir}", LogLevel.SUCCESS)
                        paths.append(subdir)
            except (PermissionError, OSError) as e:
                self._log(f"Error accessing {base_path}: {e}", LogLevel.WARNING)
        
        if not paths:
            self._log("No engines found in standard paths")
        
        return paths

    def find_all_engines(self, force_rescan: bool = False) -> Dict[str, EngineInfo]:
        """
        Find all installed Unreal Engine instances.
        
        Args:
            force_rescan: If True, ignore cached configuration
            
        Returns:
            Dictionary mapping version strings to EngineInfo objects
        """
        self._log("Starting engine discovery...")
        
        # Try loading from config first
        if not force_rescan:
            saved_engines = self._config.load_engines()
            if saved_engines:
                self._log("Loading engines from configuration...", LogLevel.INFO)
                valid_engines = {}
                
                for version, path_str in saved_engines.items():
                    path = Path(path_str)
                    if self.is_valid_engine_path(path):
                        valid_engines[version] = EngineInfo(
                            version=version,
                            path=path,
                            has_uat=True,
                            has_editor=True,
                        )
                    else:
                        self._log(
                            f"Cached engine {version} at {path} is no longer valid",
                            LogLevel.WARNING
                        )
                
                if valid_engines:
                    self._found_engines = valid_engines
                    self._log(
                        f"Loaded {len(valid_engines)} engine(s) from configuration",
                        LogLevel.SUCCESS
                    )
                    return valid_engines.copy()
                else:
                    self._log("Cached paths invalid, performing new scan", LogLevel.WARNING)

        # Perform fresh discovery
        all_paths: set[Path] = set()
        
        # Registry search
        all_paths.update(self.find_in_registry())
        
        # Environment search
        all_paths.update(self.find_in_environment())
        
        # Standard paths search
        all_paths.update(self.find_in_standard_paths())
        
        if not all_paths:
            self._log("No Unreal Engine installations found", LogLevel.WARNING)
            return {}
        
        # Process found paths
        result = self._process_found_paths(list(all_paths))
        
        if result:
            # Save to configuration
            engines_dict = {v: str(info.path) for v, info in result.items()}
            self._config.save_engines(engines_dict)
            self._log(f"Found {len(result)} engine(s)", LogLevel.SUCCESS)
        
        return result

    def _process_found_paths(self, paths: List[Path]) -> Dict[str, EngineInfo]:
        """Process discovered paths and extract version info."""
        result: Dict[str, EngineInfo] = {}
        
        for path in paths:
            # Normalize path
            if not (path / "Engine").exists() and path.name == "Engine":
                path = path.parent
            
            version = self.extract_version(path)
            if version:
                engine_info = EngineInfo(
                    version=version,
                    path=path,
                    has_uat=True,
                    has_editor=True,
                )
                result[version] = engine_info
                self._log(f"Registered engine {version}: {path}", LogLevel.SUCCESS)
            else:
                self._log(f"Could not determine version for: {path}", LogLevel.WARNING)
        
        self._found_engines = result
        return result

    def add_engine_manually(self, path: Path) -> Optional[EngineInfo]:
        """
        Manually add an engine installation.
        
        Args:
            path: Path to UE installation
            
        Returns:
            EngineInfo if valid, None otherwise
        """
        if not self.is_valid_engine_path(path):
            self._log(f"Invalid engine path: {path}", LogLevel.ERROR)
            return None
        
        version = self.extract_version(path)
        if not version:
            self._log(f"Could not determine version for: {path}", LogLevel.ERROR)
            return None
        
        engine_info = EngineInfo(
            version=version,
            path=path,
            has_uat=True,
            has_editor=True,
        )
        
        # Update found engines
        self._found_engines[version] = engine_info
        
        # Save to config
        self._config.add_engine(version, str(path))
        
        self._log(f"Added engine {version}: {path}", LogLevel.SUCCESS)
        return engine_info

    def remove_engine(self, version: str) -> bool:
        """Remove an engine from configuration."""
        if version in self._found_engines:
            del self._found_engines[version]
        return self._config.remove_engine(version)

    @property
    def found_engines(self) -> Dict[str, EngineInfo]:
        """Get currently found engines."""
        return self._found_engines.copy()
