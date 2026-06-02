"""
Core plugin builder module.
Handles plugin building without Qt dependencies.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List

from .types import (
    BuildConfig,
    BuildResult,
    BuildStatus,
    PluginInfo,
    LogLevel,
    LogMessage,
)
from ue_forge.platform import ue_platform_handler as platform_handler


LogCallback = Callable[[LogMessage], None]
ProgressCallback = Callable[[int], None]
StatusCallback = Callable[[BuildStatus], None]


class PluginBuilder:
    """
    Core plugin builder that operates without Qt dependencies.
    
    Uses subprocess for process management and callbacks for UI updates.
    Can be used in both GUI and headless environments.
    """

    def __init__(
        self,
        log_callback: Optional[LogCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        status_callback: Optional[StatusCallback] = None,
    ):
        self._log_callback = log_callback
        self._progress_callback = progress_callback
        self._status_callback = status_callback
        
        self._platform = platform_handler()
        self._process: Optional[subprocess.Popen] = None
        self._cancel_requested = False
        self._build_thread: Optional[threading.Thread] = None
        self._current_config: Optional[BuildConfig] = None

    def set_log_callback(self, callback: LogCallback) -> None:
        """Set the logging callback."""
        self._log_callback = callback

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set the progress callback."""
        self._progress_callback = callback

    def set_status_callback(self, callback: StatusCallback) -> None:
        """Set the status callback."""
        self._status_callback = callback

    def _log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """Log a message through the callback if set."""
        if self._log_callback:
            self._log_callback(LogMessage(text=message, level=level))

    def _set_progress(self, progress: int) -> None:
        """Update progress through callback if set."""
        if self._progress_callback:
            self._progress_callback(min(100, max(0, progress)))

    def _set_status(self, status: BuildStatus) -> None:
        """Update status through callback if set."""
        if self._status_callback:
            self._status_callback(status)

    @staticmethod
    def extract_plugin_info(plugin_path: Path) -> Optional[PluginInfo]:
        """
        Extract information from a .uplugin file.
        
        Args:
            plugin_path: Path to .uplugin file
            
        Returns:
            PluginInfo object or None if extraction fails
        """
        if not plugin_path.exists():
            return None

        try:
            # Use utf-8-sig to handle BOM (Byte Order Mark)
            with open(plugin_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return PluginInfo.from_dict(data, plugin_path)
        except (json.JSONDecodeError, IOError, KeyError):
            return None

    def get_uat_path(self, engine_path: Path) -> Optional[Path]:
        """Get path to RunUAT script for given engine."""
        uat_name = self._platform.get_uat_script_name()
        uat_path = engine_path / "Engine" / "Build" / "BatchFiles" / uat_name
        return uat_path if uat_path.exists() else None

    def build_command(self, config: BuildConfig) -> List[str]:
        """
        Build the UAT command from configuration.
        
        Args:
            config: Build configuration
            
        Returns:
            List of command arguments
        """
        uat_path = self.get_uat_path(config.engine_path)
        if not uat_path:
            raise ValueError(f"RunUAT not found in engine path: {config.engine_path}")

        # Normalize paths
        plugin_path = config.plugin_path.resolve()
        output_path = config.output_path.resolve()

        command = [
            str(uat_path),
            "BuildPlugin",
            f"-Plugin={plugin_path}",
            f"-Package={output_path}",
        ]

        # Add parameters from config
        params = config.get_all_params()
        for param_name, value in params.items():
            if value is True:
                # Boolean flag
                command.append(f"-{param_name}")
            elif value not in (False, None, ""):
                # Key-value parameter
                command.append(f"-{param_name}={value}")

        return command

    def get_command_string(self, config: BuildConfig) -> str:
        """
        Get a human-readable command string for display.
        
        Args:
            config: Build configuration
            
        Returns:
            Command string suitable for copy/paste
        """
        try:
            command = self.build_command(config)
        except ValueError:
            return ""

        # Format for display
        result_parts = [command[0], command[1]]  # UAT path and BuildPlugin

        for arg in command[2:]:
            if "=" in arg:
                key, value = arg.split("=", 1)
                # Quote paths with spaces
                if " " in value or "\\" in value:
                    value = value.replace("\\", "/")
                    result_parts.append(f'{key}="{value}"')
                else:
                    result_parts.append(arg)
            else:
                result_parts.append(arg)

        return " ".join(result_parts)

    def _classify_log_line(self, line: str) -> LogLevel:
        """Classify a log line to determine its severity level."""
        line_lower = line.lower()
        
        # Error patterns
        if re.search(r'\berror\b|failed|\[error\]', line_lower):
            return LogLevel.ERROR
        
        # Warning patterns
        if re.search(r'\bwarning\b|\[warning\]', line_lower):
            return LogLevel.WARNING
        
        # Success patterns
        if re.search(r'\bsuccess\b|\bcompleted\b|\bfinished\b', line_lower):
            return LogLevel.SUCCESS
        
        return LogLevel.INFO

    def _extract_progress(self, line: str) -> Optional[int]:
        """Extract progress percentage from log line."""
        # Match patterns like [1/25], 50%, etc.
        
        # Fraction pattern: [X/Y]
        fraction_match = re.search(r'\[(\d+)/(\d+)\]', line)
        if fraction_match:
            current = int(fraction_match.group(1))
            total = int(fraction_match.group(2))
            if total > 0:
                return int((current / total) * 100)
        
        # Percentage pattern
        percent_match = re.search(r'(\d+)%', line)
        if percent_match:
            return int(percent_match.group(1))
        
        return None

    def build_plugin(
        self,
        config: BuildConfig,
        blocking: bool = True,
    ) -> Optional[BuildResult]:
        """
        Build a plugin.
        
        Args:
            config: Build configuration
            blocking: If True, wait for build to complete
            
        Returns:
            BuildResult if blocking, None if async
        """
        self._current_config = config
        self._cancel_requested = False

        # Validate inputs
        if not config.plugin_path.exists():
            self._log(f"Plugin file not found: {config.plugin_path}", LogLevel.ERROR)
            return BuildResult(
                status=BuildStatus.FAILED,
                exit_code=-1,
                message=f"Plugin file not found: {config.plugin_path}",
            )

        uat_path = self.get_uat_path(config.engine_path)
        if not uat_path:
            self._log(f"RunUAT not found: {config.engine_path}", LogLevel.ERROR)
            return BuildResult(
                status=BuildStatus.FAILED,
                exit_code=-1,
                message=f"RunUAT not found in engine: {config.engine_path}",
            )

        # Create output directory
        try:
            config.output_path.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            self._log(f"Cannot create output directory: {e}", LogLevel.ERROR)
            return BuildResult(
                status=BuildStatus.FAILED,
                exit_code=-1,
                message=f"Cannot create output directory: {e}",
            )

        if blocking:
            return self._run_build_sync(config)
        else:
            self._build_thread = threading.Thread(
                target=self._run_build_async,
                args=(config,),
                daemon=True,
            )
            self._build_thread.start()
            return None

    def _run_build_sync(self, config: BuildConfig) -> BuildResult:
        """Run build synchronously."""
        start_time = time.time()
        errors: List[str] = []
        warnings: List[str] = []

        try:
            command = self.build_command(config)
        except ValueError as e:
            return BuildResult(
                status=BuildStatus.FAILED,
                exit_code=-1,
                message=str(e),
            )

        self._log(f"Build command: {self.get_command_string(config)}", LogLevel.INFO)
        self._set_status(BuildStatus.RUNNING)
        self._set_progress(0)

        try:
            # Start process
            # On Windows: CREATE_NO_WINDOW hides console, CREATE_NEW_PROCESS_GROUP allows cancellation
            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                creationflags=creation_flags,
            )

            # Process output
            if self._process.stdout:
                for line in iter(self._process.stdout.readline, ""):
                    if self._cancel_requested:
                        break

                    line = line.rstrip()
                    if not line:
                        continue

                    level = self._classify_log_line(line)
                    self._log(line, level)

                    if level == LogLevel.ERROR:
                        errors.append(line)
                    elif level == LogLevel.WARNING:
                        warnings.append(line)

                    progress = self._extract_progress(line)
                    if progress is not None:
                        self._set_progress(progress)

            self._process.wait()
            exit_code = self._process.returncode

        except Exception as e:
            self._log(f"Build process error: {e}", LogLevel.ERROR)
            return BuildResult(
                status=BuildStatus.FAILED,
                exit_code=-1,
                message=str(e),
                duration_seconds=time.time() - start_time,
                errors=errors,
                warnings=warnings,
            )
        finally:
            self._process = None

        duration = time.time() - start_time

        if self._cancel_requested:
            self._set_status(BuildStatus.CANCELLED)
            return BuildResult(
                status=BuildStatus.CANCELLED,
                exit_code=-1,
                message="Build cancelled by user",
                duration_seconds=duration,
                errors=errors,
                warnings=warnings,
            )

        if exit_code == 0:
            self._log("Build completed successfully", LogLevel.SUCCESS)
            self._set_status(BuildStatus.SUCCESS)
            self._set_progress(100)
            return BuildResult(
                status=BuildStatus.SUCCESS,
                exit_code=0,
                message="Build completed successfully",
                duration_seconds=duration,
                output_path=config.output_path,
                errors=errors,
                warnings=warnings,
            )
        else:
            self._log(f"Build failed with exit code {exit_code}", LogLevel.ERROR)
            self._set_status(BuildStatus.FAILED)
            return BuildResult(
                status=BuildStatus.FAILED,
                exit_code=exit_code,
                message=f"Build failed with exit code {exit_code}",
                duration_seconds=duration,
                errors=errors,
                warnings=warnings,
            )

    def _run_build_async(self, config: BuildConfig) -> None:
        """Run build asynchronously in a thread."""
        self._run_build_sync(config)

    def cancel_build(self) -> bool:
        """
        Cancel the current build.
        
        Returns:
            True if cancellation was initiated
        """
        if self._process is None:
            return False

        self._cancel_requested = True
        self._log("Cancelling build...", LogLevel.WARNING)

        try:
            pid = self._process.pid
            if pid:
                success = self._platform.kill_process_tree(pid)
                if success:
                    self._log("Build process terminated", LogLevel.WARNING)
                else:
                    # Fallback: terminate directly
                    self._process.terminate()
                    self._process.wait(timeout=5)
        except Exception as e:
            self._log(f"Error cancelling build: {e}", LogLevel.ERROR)
            return False

        # Clean up incomplete output
        if self._current_config and self._current_config.output_path.exists():
            try:
                shutil.rmtree(self._current_config.output_path, ignore_errors=True)
                self._log(f"Removed incomplete output: {self._current_config.output_path}", LogLevel.INFO)
            except Exception:
                pass

        self._set_status(BuildStatus.CANCELLED)
        return True

    @property
    def is_running(self) -> bool:
        """Check if a build is currently running."""
        return self._process is not None and self._process.poll() is None


def parse_extra_params(params_string: str) -> Dict[str, Any]:
    """
    Parse extra command-line parameters string.
    
    Handles quoted values correctly:
    -Param1=Value1 -Flag -Param2="Value with spaces"
    
    Args:
        params_string: String of parameters
        
    Returns:
        Dictionary of parameter names to values
    """
    result: Dict[str, Any] = {}
    
    if not params_string.strip():
        return result

    # Use shlex to properly handle quotes
    try:
        tokens = shlex.split(params_string)
    except ValueError:
        # Fallback to simple split if shlex fails
        tokens = params_string.split()

    for token in tokens:
        if not token.startswith("-"):
            continue
        
        param = token[1:]  # Remove leading dash
        
        if "=" in param:
            key, value = param.split("=", 1)
            # Remove surrounding quotes if present
            value = value.strip("\"'")
            result[key] = value
        else:
            result[param] = True

    return result
