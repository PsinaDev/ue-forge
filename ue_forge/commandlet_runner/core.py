"""
Commandlet discovery and execution engine.

Scans Unreal Engine and project source directories for commandlet classes,
extracts descriptions from code comments, and builds/executes command lines.

Pure Python — no Qt dependencies.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from ue_forge.shared.types import LogLevel, LogMessage


LogCallback = Callable[[LogMessage], None]
ProgressCallback = Callable[[int], None]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class CommandletSource(Enum):
    ENGINE = "engine"
    PROJECT = "project"


@dataclass
class CommandletParam:
    """A discovered commandlet parameter or switch."""
    name: str
    description: str = ""
    has_value: bool = False
    default_value: str = ""


@dataclass
class CommandletInfo:
    """Information about a discovered commandlet."""
    name: str              # e.g. "ResavePackages" (without U prefix and Commandlet suffix)
    class_name: str        # e.g. "UResavePackagesCommandlet"
    source_file: str       # relative path to header (display)
    description: str       # extracted from comments above class
    source: CommandletSource
    help_text: str = ""    # extended help from code
    source_path: str = ""  # absolute path to header (for "Open" action)
    params: list[CommandletParam] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)  # usage examples from comments

    @property
    def display_name(self) -> str:
        """Human-readable name with spaces inserted at camel-case boundaries."""
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", self.name)

    @property
    def auto_usage(self) -> str:
        """Auto-generate a usage summary from discovered parameters.

        Returns empty string if no params discovered.
        """
        if not self.params:
            return ""
        parts: list[str] = []
        for p in self.params:
            if p.has_value:
                parts.append(f"-{p.name}=<value>")
            else:
                parts.append(f"-{p.name}")
        return "Discovered parameters:  " + "  ".join(parts)


class RunStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunResult:
    status: RunStatus
    exit_code: int
    message: str
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Match class declarations inheriting from UCommandlet (directly or indirectly)
_CLASS_RE = re.compile(
    r"^\s*(?:UCLASS\b[^)]*\)\s*)?"
    r"class\s+(?:\w+_API\s+)?"       # optional API macro
    r"(U\w+Commandlet)\s*"           # class name (capture group 1)
    r":\s*public\s+(\w+)",           # parent class (capture group 2)
    re.MULTILINE,
)

# Extract commandlet name from class name: UResavePackagesCommandlet -> ResavePackages
_NAME_FROM_CLASS_RE = re.compile(r"^U(.+?)Commandlet$")

# Comment block immediately before a class declaration
_COMMENT_BLOCK_RE = re.compile(
    r"(/\*\*[\s\S]*?\*/|(?://[^\n]*\n)+)\s*$"
)

# Parameter patterns found in commandlet source
_PARAM_PATTERNS = [
    # FParse::Param(Params, TEXT("ParamName"), Value)
    re.compile(r'FParse::Param\s*\([^,]+,\s*TEXT\(\s*"(-?\w+)"\s*\)', re.IGNORECASE),
    # FParse::Value(Params, TEXT("ParamName"), Value)
    re.compile(r'FParse::Value\s*\([^,]+,\s*TEXT\(\s*"(-?\w+)"\s*\)', re.IGNORECASE),
    # Switches.Contains(TEXT("switch"))
    re.compile(r'Switches\.Contains\s*\(\s*TEXT\(\s*"(-?\w+)"\s*\)', re.IGNORECASE),
    # Params.Contains(TEXT("-switch"))
    re.compile(r'Contains\s*\(\s*TEXT\(\s*"-(\w+)"\s*\)', re.IGNORECASE),
    # ParseCommandLine helper patterns
    re.compile(r'TEXT\(\s*"-(\w+)="\s*\)', re.IGNORECASE),
    re.compile(r'TEXT\(\s*"-(\w+)"\s*\)', re.IGNORECASE),
]

# Directories to skip during recursive scanning
_SKIP_DIRS = {
    "Binaries", "Intermediate", "DerivedDataCache", "Saved",
    "ThirdParty", ".git", ".svn", "__pycache__", "node_modules",
    "Content",
}

# Pattern to extract TEXT("...") content from UE_LOG calls
_UE_LOG_TEXT_RE = re.compile(
    r'UE_LOG\s*\([^,]+,\s*\w+,\s*TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)',
    re.MULTILINE,
)

# Pattern to parse help parameter lines like:
#   " Required: -targetPlatform=<platform>     (Description here"
#   " Optional: -noglobals                     (Don't do global shaders)"
_HELP_PARAM_RE = re.compile(
    r"^\s*(?:Required|Optional)?:?\s*"  # Optional "Required:" or "Optional:" prefix
    r"-(\w+)"                            # Parameter name
    r"(?:=<[^>]+>|=\S+)?"               # Optional =<value> or =VALUE
    r"\s*"                               # Whitespace
    r"(?:\((.+?)\)?)?$",                 # Optional (description)
    re.IGNORECASE,
)

# Alternative help param pattern: "-param    Description without parens"
_HELP_PARAM_ALT_RE = re.compile(
    r"^\s*-(\w+)"                        # -param
    r"(?:=<[^>]+>|=\S+)?"               # Optional =<value>
    r"\s{2,}"                            # At least 2 spaces separator
    r"(.+)$",                            # Description
)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def _clean_comment(raw: str) -> str:
    """Strip comment markers and normalize whitespace."""
    # Remove /** ... */ markers
    text = re.sub(r"/\*\*?", "", raw)
    text = re.sub(r"\*/", "", text)
    # Remove // markers
    text = re.sub(r"^\s*//+\s?", "", text, flags=re.MULTILINE)
    # Remove @brief, @note etc.
    text = re.sub(r"@\w+\s*", "", text)
    # Remove leading * from doc-comment lines
    text = re.sub(r"^\s*\*\s?", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    lines = [ln.strip() for ln in text.strip().splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def _extract_description(file_text: str, class_match_start: int) -> str:
    """Extract the comment block right before a class declaration."""
    before = file_text[:class_match_start]
    # Try multi-line /** ... */
    m = re.search(r"/\*\*([\s\S]*?)\*/\s*$", before)
    if m:
        return _clean_comment(m.group(0))
    # Try consecutive // lines
    lines: list[str] = []
    for line in reversed(before.splitlines()):
        stripped = line.strip()
        if stripped.startswith("//"):
            lines.append(stripped)
        elif stripped == "" and lines:
            continue
        else:
            break
    if lines:
        lines.reverse()
        return _clean_comment("\n".join(lines))
    return ""


def _extract_params_from_cpp(cpp_path: Path) -> list[CommandletParam]:
    """Scan a .cpp file for parameter usage patterns."""
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    found: dict[str, CommandletParam] = {}
    for pattern in _PARAM_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1).lstrip("-")
            if name and name not in found and len(name) > 1:
                has_value = "Value" in pattern.pattern or "=" in pattern.pattern
                found[name] = CommandletParam(
                    name=name,
                    has_value=has_value,
                )
    return list(found.values())


def _extract_help_text(cpp_path: Path) -> str:
    """Try to extract HelpDescription or help text from constructor."""
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    # Look for HelpDescription assignment
    m = re.search(
        r'HelpDescription\s*=\s*TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)',
        text,
    )
    if m:
        return m.group(1).replace("\\n", "\n").replace('\\"', '"')

    # Look for HelpUsage
    m = re.search(
        r'HelpUsage\s*=\s*TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)',
        text,
    )
    if m:
        return m.group(1).replace("\\n", "\n").replace('\\"', '"')

    return ""


def _find_help_block(text: str) -> Optional[str]:
    """
    Find the help block in Main() that handles -help switch.

    Looks for patterns like:
        if (Switches.Contains("help"))
        if (Switches.Contains(TEXT("help")))
        if (FParse::Param(..., TEXT("help")))
    """
    # Patterns that indicate start of help block
    help_patterns = [
        r'Switches\.Contains\s*\(\s*(?:TEXT\()?\s*"help"',
        r'FParse::Param\s*\([^,]+,\s*TEXT\(\s*"help"\s*\)',
        r'Contains\s*\(\s*TEXT\(\s*"-?help"\s*\)',
    ]

    for pattern in help_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            # Find the opening brace after this match
            start = m.end()
            brace_pos = text.find("{", start)
            if brace_pos == -1 or brace_pos > start + 50:
                continue

            # Extract balanced braces block
            depth = 1
            pos = brace_pos + 1
            while pos < len(text) and depth > 0:
                if text[pos] == "{":
                    depth += 1
                elif text[pos] == "}":
                    depth -= 1
                pos += 1

            if depth == 0:
                return text[brace_pos + 1:pos - 1]

    return None


def _parse_help_block(help_block: str) -> tuple[str, list[CommandletParam]]:
    """
    Parse UE_LOG calls inside a help block to extract description and params.

    Returns:
        tuple of (description, list of CommandletParam)
    """
    description_lines: list[str] = []
    params: dict[str, CommandletParam] = {}

    # Extract all TEXT("...") from UE_LOG calls
    for m in _UE_LOG_TEXT_RE.finditer(help_block):
        line = m.group(1).replace("\\n", "\n").replace('\\"', '"').strip()
        if not line:
            continue

        # Check if this line describes a parameter
        param_match = _HELP_PARAM_RE.match(line)
        if param_match:
            param_name = param_match.group(1)
            param_desc = param_match.group(2) or ""
            # Clean up trailing )
            param_desc = param_desc.rstrip(")")
            has_value = "=" in line or "<" in line
            if param_name.lower() not in ("run", "help"):
                params[param_name] = CommandletParam(
                    name=param_name,
                    description=param_desc.strip(),
                    has_value=has_value,
                )
            continue

        # Try alternative format
        alt_match = _HELP_PARAM_ALT_RE.match(line)
        if alt_match:
            param_name = alt_match.group(1)
            param_desc = alt_match.group(2)
            has_value = "=" in line or "<" in line
            if param_name.lower() not in ("run", "help"):
                params[param_name] = CommandletParam(
                    name=param_name,
                    description=param_desc.strip(),
                    has_value=has_value,
                )
            continue

        # Check for "Options:" header line — skip it
        if line.lower() in ("options:", "parameters:", "usage:", "switches:"):
            continue

        # Otherwise it's part of the description
        # Skip lines that are just the commandlet name or headers
        if not any(x in line.lower() for x in ("required:", "optional:", "---")):
            description_lines.append(line)

    # Join description, removing the commandlet name line if it's just the name
    description = "\n".join(description_lines).strip()

    return description, list(params.values())


def _extract_usage_examples(cpp_path: Path) -> list[str]:
    """
    Extract usage examples from comments at the top of .cpp file.

    Looks for patterns like:
        // Examples
        // UnrealEditor-Cmd.exe <proj> -run=CommandletName ...
    """
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    examples: list[str] = []

    # Look for Examples section in comments
    lines = text.split("\n")
    in_examples = False

    for i, line in enumerate(lines[:150]):  # Only check first 150 lines
        stripped = line.strip()

        # Check for "Examples" marker
        if stripped.startswith("//") and "example" in stripped.lower():
            in_examples = True
            continue

        if in_examples:
            if stripped.startswith("//"):
                # Extract the example command
                example = stripped.lstrip("/").strip()
                # Only include if it looks like a command line
                if example and ("-run=" in example or "Editor" in example):
                    examples.append(example)
            elif stripped and not stripped.startswith("//"):
                # End of comment block
                break

    return examples


def _extract_help_block_data(cpp_path: Path) -> tuple[str, list[CommandletParam], list[str]]:
    """
    Extract description, params, and examples from .cpp help block.

    This is the main entry point for .cpp parsing that handles the
    common UE pattern of printing help via UE_LOG in Main().

    Returns:
        tuple of (description, params, examples)
    """
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", [], []

    description = ""
    params: list[CommandletParam] = []

    # Try to find and parse help block
    help_block = _find_help_block(text)
    if help_block:
        description, params = _parse_help_block(help_block)

    # Get usage examples
    examples = _extract_usage_examples(cpp_path)

    return description, params, examples


def _extract_cpp_description(cpp_path: Path, class_name: str) -> str:
    """
    Extract description from comment block above the constructor in .cpp.

    Many UE commandlets have their usage/description as a ``/** ... */``
    block right before the constructor definition, not in the header.
    """
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    # Find constructor: UClassName::UClassName(
    ctor_pattern = re.compile(
        re.escape(class_name) + r"::" + re.escape(class_name) + r"\s*\(",
    )
    m = ctor_pattern.search(text)
    if not m:
        return ""

    before = text[:m.start()]

    # Try /** ... */ block
    cm = re.search(r"/\*\*?([\s\S]*?)\*/\s*$", before)
    if cm:
        cleaned = _clean_comment(cm.group(0))
        # Skip trivial single-word comments (just the class name)
        if cleaned and len(cleaned) > 20:
            return cleaned

    # Try consecutive // lines
    lines: list[str] = []
    for line in reversed(before.splitlines()):
        stripped = line.strip()
        if stripped.startswith("//"):
            lines.append(stripped)
        elif stripped == "" and lines:
            continue
        else:
            break
    if lines:
        lines.reverse()
        cleaned = _clean_comment("\n".join(lines))
        if cleaned and len(cleaned) > 20:
            return cleaned

    return ""


def _find_matching_cpp(header: Path) -> Optional[Path]:
    """
    Find the .cpp file corresponding to a header file.

    UE projects typically split headers and sources:
      - Classes/Commandlets/Foo.h  -> Private/Commandlets/Foo.cpp
      - Public/Commandlets/Foo.h   -> Private/Commandlets/Foo.cpp
      - Foo.h                      -> Foo.cpp (same directory)

    Returns the path to the .cpp file if found, None otherwise.
    """
    cpp_name = header.stem + ".cpp"

    # 1. Try same directory first
    same_dir = header.with_suffix(".cpp")
    if same_dir.exists():
        return same_dir

    # 2. Try Classes -> Private substitution
    header_str = str(header)
    if "/Classes/" in header_str or "\\Classes\\" in header_str:
        cpp_path = Path(
            header_str
            .replace("/Classes/", "/Private/")
            .replace("\\Classes\\", "\\Private\\")
        ).with_suffix(".cpp")
        if cpp_path.exists():
            return cpp_path

    # 3. Try Public -> Private substitution
    if "/Public/" in header_str or "\\Public\\" in header_str:
        cpp_path = Path(
            header_str
            .replace("/Public/", "/Private/")
            .replace("\\Public\\", "\\Private\\")
        ).with_suffix(".cpp")
        if cpp_path.exists():
            return cpp_path

    # 4. Try searching in sibling Private folder
    # e.g., .../SomeModule/Classes/Foo.h -> .../SomeModule/Private/Foo.cpp
    parts = header.parts
    for i, part in enumerate(parts):
        if part in ("Classes", "Public"):
            # Build path with Private instead
            private_parts = parts[:i] + ("Private",) + parts[i + 1:]
            cpp_path = Path(*private_parts).with_suffix(".cpp")
            if cpp_path.exists():
                return cpp_path

    # 5. Try searching in module's Private subfolder with same relative path
    # e.g., .../Module/Classes/Sub/Foo.h -> .../Module/Private/Sub/Foo.cpp
    for i, part in enumerate(parts):
        if part in ("Classes", "Public"):
            # Get relative path after Classes/Public
            rel_parts = parts[i + 1:]
            # Build Private path
            private_base = Path(*parts[:i]) / "Private"
            if private_base.is_dir():
                cpp_path = private_base.joinpath(*rel_parts).with_suffix(".cpp")
                if cpp_path.exists():
                    return cpp_path

    return None


def scan_directory(
    root: Path,
    source: CommandletSource,
    progress_callback: Optional[ProgressCallback] = None,
) -> list[CommandletInfo]:
    """
    Recursively scan a directory for commandlet class declarations.

    Uses os.walk with directory pruning to avoid stack overflow
    on large UE projects (known issue with rglob).
    """
    commandlets: list[CommandletInfo] = []
    header_files: list[Path] = []

    # Phase 1: collect header files
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skippable directories in-place
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".h"):
                header_files.append(Path(dirpath) / fn)

    total = len(header_files)
    if total == 0:
        return commandlets

    # Phase 2: scan headers for commandlet classes
    for idx, header in enumerate(header_files):
        if progress_callback and idx % 50 == 0:
            progress_callback(int((idx / total) * 100))

        try:
            text = header.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for m in _CLASS_RE.finditer(text):
            class_name = m.group(1)
            parent_class = m.group(2)

            # Must inherit from UCommandlet or *Commandlet parent
            if "Commandlet" not in parent_class and parent_class != "UCommandlet":
                continue

            name_m = _NAME_FROM_CLASS_RE.match(class_name)
            if not name_m:
                continue

            cmdlet_name = name_m.group(1)
            description = _extract_description(text, m.start())

            # Try to find matching .cpp for params and help text
            cpp_path = _find_matching_cpp(header)
            params: list[CommandletParam] = []
            help_text = ""
            examples: list[str] = []

            if cpp_path:
                # First, get basic params from code patterns
                basic_params = _extract_params_from_cpp(cpp_path)

                # Then try to extract rich data from help block (UE_LOG in -help handler)
                help_desc, help_params, examples = _extract_help_block_data(cpp_path)

                # Merge params: help_params have descriptions, basic_params may have extras
                params_dict: dict[str, CommandletParam] = {}

                # Add basic params first
                for p in basic_params:
                    params_dict[p.name.lower()] = p

                # Override/add with help params (they have descriptions)
                for p in help_params:
                    existing = params_dict.get(p.name.lower())
                    if existing:
                        # Keep has_value from either source
                        existing.description = p.description
                        existing.has_value = existing.has_value or p.has_value
                    else:
                        params_dict[p.name.lower()] = p

                params = list(params_dict.values())

                # Try HelpDescription field
                help_text = _extract_help_text(cpp_path)

                # Use help block description if we have one and no header description
                if help_desc and not description:
                    description = help_desc

                # Fallback: extract description from .cpp comment block
                # above constructor (many UE commandlets document there)
                if not description:
                    description = _extract_cpp_description(cpp_path, class_name)

            try:
                rel = str(header.relative_to(root))
            except ValueError:
                rel = str(header)

            commandlets.append(CommandletInfo(
                name=cmdlet_name,
                class_name=class_name,
                source_file=rel,
                description=description,
                source=source,
                help_text=help_text,
                source_path=str(header),
                params=params,
                examples=examples,
            ))

    if progress_callback:
        progress_callback(100)

    return commandlets


# ---------------------------------------------------------------------------
# Engine / project resolution
# ---------------------------------------------------------------------------

def resolve_engine_path(project_path: Path) -> Optional[Path]:
    """
    Resolve the engine installation path for a .uproject file.

    Checks EngineAssociation in .uproject, then looks up the engine
    via registry / known paths / config.
    """
    if not project_path.exists():
        return None

    try:
        data = json.loads(project_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    assoc = data.get("EngineAssociation", "")

    # If it's a path (source build)
    if assoc and (Path(assoc) / "Engine").is_dir():
        return Path(assoc)

    # Try to find via config manager
    from ue_forge.shared.config import get_config_manager
    config = get_config_manager()
    engines = config.load_engines()

    if not engines:
        # Try auto-discovery
        from ue_forge.plugin_builder.engine_finder import EngineFinder
        finder = EngineFinder()
        found = finder.find_all_engines()
        engines = {v: str(info.path) for v, info in found.items()}

    if not engines:
        return None

    # Match by version association
    for version, path_str in engines.items():
        if assoc and version == assoc:
            engine = Path(path_str)
            if (engine / "Engine").is_dir():
                return engine

    # If association is a GUID, try matching via registry
    # Fall back to latest available engine
    if engines:
        # Prefer highest version
        latest = sorted(engines.keys(), reverse=True)[0]
        engine = Path(engines[latest])
        if (engine / "Engine").is_dir():
            return engine

    return None


def get_editor_cmd_path(engine_path: Path) -> Optional[Path]:
    """Get path to UnrealEditor-Cmd executable."""
    from ue_forge.shared.platform_utils import platform_handler
    handler = platform_handler()
    binaries = handler.get_binaries_subdir()

    # UE5: UnrealEditor-Cmd
    cmd_name = "UnrealEditor-Cmd"
    if binaries == "Win64":
        cmd_name += ".exe"
    cmd_path = engine_path / "Engine" / "Binaries" / binaries / cmd_name
    if cmd_path.exists():
        return cmd_path

    # UE4: UE4Editor-Cmd
    cmd_name = "UE4Editor-Cmd"
    if binaries == "Win64":
        cmd_name += ".exe"
    cmd_path = engine_path / "Engine" / "Binaries" / binaries / cmd_name
    if cmd_path.exists():
        return cmd_path

    # Fallback: full editor
    editor_name = handler.get_editor_executable_name()
    editor_path = engine_path / "Engine" / "Binaries" / binaries / editor_name
    if editor_path.exists():
        return editor_path

    return None


# ---------------------------------------------------------------------------
# Command building and execution
# ---------------------------------------------------------------------------

def build_command(
    editor_cmd: Path,
    project_path: Path,
    commandlet_name: str,
    params: list[str],
    dry_run: bool = False,
) -> list[str]:
    """Build the commandlet command line."""
    cmd = [str(editor_cmd), str(project_path)]
    cmd.append(f"-run={commandlet_name}")

    for p in params:
        p = p.strip()
        if p:
            if not p.startswith("-"):
                p = f"-{p}"
            cmd.append(p)

    if dry_run:
        # Many commandlets support -WhatIf or similar; we add common ones
        # The user can also manually add dry-run flags
        pass

    # Standard flags for commandlet execution
    cmd.extend(["-unattended", "-nopause"])

    return cmd


def run_commandlet(
    editor_cmd: Path,
    project_path: Path,
    commandlet_name: str,
    params: list[str],
    log_callback: Optional[LogCallback] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
    process_holder: Optional[object] = None,
) -> RunResult:
    """Execute a commandlet and stream output.

    Args:
        process_holder: If provided, the subprocess.Popen object is stored
            as ``process_holder._process`` so the caller can force-kill it.
    """
    start = time.monotonic()

    cmd = build_command(editor_cmd, project_path, commandlet_name, params)

    if log_callback:
        log_callback(LogMessage(
            text=f"> {' '.join(cmd)}",
            level=LogLevel.INFO,
        ))

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(project_path.parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as e:
        msg = f"Editor not found: {e}"
        if log_callback:
            log_callback(LogMessage(text=msg, level=LogLevel.ERROR))
        return RunResult(
            status=RunStatus.FAILED, exit_code=-1, message=msg,
            duration_seconds=time.monotonic() - start,
        )
    except OSError as e:
        msg = f"Failed to start process: {e}"
        if log_callback:
            log_callback(LogMessage(text=msg, level=LogLevel.ERROR))
        return RunResult(
            status=RunStatus.FAILED, exit_code=-1, message=msg,
            duration_seconds=time.monotonic() - start,
        )

    # Store process reference so caller can force-kill on cancel
    if process_holder is not None:
        process_holder._process = process

    try:
        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n\r")
            if log_callback:
                level = LogLevel.INFO
                lower = line.lower()
                if "error" in lower or "fatal" in lower:
                    level = LogLevel.ERROR
                elif "warning" in lower:
                    level = LogLevel.WARNING
                elif "success" in lower or "complete" in lower:
                    level = LogLevel.SUCCESS
                log_callback(LogMessage(text=line, level=level))

            if cancel_check and cancel_check():
                process.kill()
                if log_callback:
                    log_callback(LogMessage(
                        text="Cancelled by user", level=LogLevel.WARNING,
                    ))
                return RunResult(
                    status=RunStatus.CANCELLED,
                    exit_code=-1,
                    message="Cancelled by user",
                    duration_seconds=time.monotonic() - start,
                )

        process.wait()
    except Exception as e:
        process.kill()
        msg = f"Process error: {e}"
        if log_callback:
            log_callback(LogMessage(text=msg, level=LogLevel.ERROR))
        return RunResult(
            status=RunStatus.FAILED,
            exit_code=-1,
            message=msg,
            duration_seconds=time.monotonic() - start,
        )

    elapsed = time.monotonic() - start
    if process.returncode == 0:
        if log_callback:
            log_callback(LogMessage(
                text=f"Completed successfully in {elapsed:.1f}s",
                level=LogLevel.SUCCESS,
            ))
        return RunResult(
            status=RunStatus.SUCCESS,
            exit_code=0,
            message="Commandlet completed successfully",
            duration_seconds=elapsed,
        )
    else:
        msg = f"Commandlet exited with code {process.returncode}"
        if log_callback:
            log_callback(LogMessage(text=msg, level=LogLevel.ERROR))
        return RunResult(
            status=RunStatus.FAILED,
            exit_code=process.returncode,
            message=f"Commandlet exited with code {process.returncode}",
            duration_seconds=elapsed,
        )