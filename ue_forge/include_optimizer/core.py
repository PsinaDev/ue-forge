"""
Core engine for Unreal Engine source include optimization.

Operates without Qt dependencies. Uses callbacks for progress reporting.
Three optimizations:
    1. Add missing ``UE_INLINE_GENERATED_CPP_BY_NAME`` macros.
    2. Replace ``CoreMinimal.h`` with specific headers based on usage analysis.
    3. Remove duplicate ``#include`` lines.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from framekit.types import LogLevel, LogMessage

logger = logging.getLogger(__name__)

LogCallback = Callable[[LogMessage], None]
ProgressCallback = Callable[[int], None]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class OptimizeStatus(Enum):
    """Result status of an optimization run."""
    SUCCESS = "success"
    FAILED = "failed"


class ChangeType(Enum):
    """Kind of optimization change."""
    ADD_INLINE_GENERATED = "add_inline_generated"
    REPLACE_COREMINIMAL = "replace_coreminimal"
    REMOVE_DUPLICATE = "remove_duplicate"
    FIX_PREPROCESSOR_INCLUDE = "fix_preprocessor_include"


@dataclass
class IncludeChange:
    """A single optimization change in one file."""
    change_type: ChangeType
    category: str
    file_path: str          # relative to source root
    old_value: str
    new_value: str
    line_number: int = 0
    source_label: str = ""  # "" = project, "PluginName" = plugin


@dataclass
class OptimizeScope:
    """Controls which optimizations are applied."""
    add_inline_generated: bool = True
    replace_coreminimal: bool = True
    remove_duplicates: bool = True
    fix_preprocessor_includes: bool = True
    create_backup: bool = True
    include_plugins: bool = False
    excluded_plugins: set[str] = field(default_factory=set)


@dataclass
class OptimizeResult:
    """Outcome of an optimization run."""
    status: OptimizeStatus
    message: str
    changes_applied: int = 0
    files_modified: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    backup_path: Path | None = None


@dataclass
class PluginInfo:
    """Discovered plugin inside a UE project."""
    name: str
    path: Path          # path to .uplugin file
    category: str
    source_dir: Path | None  # Source/ dir if it exists


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SKIP_DIRS = {
    'Binaries', 'Intermediate', 'DerivedDataCache', 'Saved',
    '.git', '.svn', '__pycache__', 'node_modules',
    'ThirdParty',
}

_SOURCE_EXTENSIONS = {'.h', '.hpp', '.cpp', '.cc', '.inl'}

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
_INCLUDE_LINE_RE = re.compile(r'^(\s*#\s*include\s+[<"][^>"]+[>"])\s*$', re.MULTILINE)
_COREMINIMAL_RE = re.compile(r'^\s*#\s*include\s+"CoreMinimal\.h"\s*$', re.MULTILINE)
_GENERATED_BODY_RE = re.compile(r'\bGENERATED_(?:BODY|UCLASS_BODY|USTRUCT_BODY)\b')
_INLINE_GENERATED_RE = re.compile(r'\bUE_INLINE_GENERATED_CPP_BY_NAME\b')
_LAST_INCLUDE_RE = re.compile(r'^(\s*#\s*include\s+[<"][^>"]+[>"])\s*$', re.MULTILINE)

_PP_IF_RE = re.compile(r'^\s*#\s*(?:if|ifdef|ifndef)\b')
_PP_ENDIF_RE = re.compile(r'^\s*#\s*endif\b')
_PP_ELSE_RE = re.compile(r'^\s*#\s*(?:else|elif)\b')
_INLINE_GENERATED_LINE_RE = re.compile(
    r'^\s*#\s*include\s+UE_INLINE_GENERATED_CPP_BY_NAME\s*\(.+?\)\s*$',
    re.MULTILINE,
)

# ---------------------------------------------------------------------------
# CoreMinimal → specific headers mapping
# ---------------------------------------------------------------------------
# Pattern → header. Scanned against file content (outside #include lines).
# CoreTypes.h is always added as baseline (int32, uint8, TEXT(), TCHAR,
# FORCEINLINE, check/ensure, platform macros, etc.).

_TYPE_HEADER_MAP: list[tuple[re.Pattern[str], str]] = [
    # Containers
    (re.compile(r'\bTArray\s*<'), 'Containers/Array.h'),
    (re.compile(r'\bTArrayView\s*<'), 'Containers/ArrayView.h'),
    (re.compile(r'\bFString\b'), 'Containers/UnrealString.h'),
    (re.compile(r'\bTMap\s*<'), 'Containers/Map.h'),
    (re.compile(r'\bTMultiMap\s*<'), 'Containers/Map.h'),
    (re.compile(r'\bTSet\s*<'), 'Containers/Set.h'),
    (re.compile(r'\bTOptional\s*<'), 'Misc/Optional.h'),
    (re.compile(r'\bTVariant\s*<'), 'Misc/Variant.h'),
    (re.compile(r'\bTBitArray\b'), 'Containers/BitArray.h'),
    (re.compile(r'\bTSparseArray\b'), 'Containers/SparseArray.h'),
    (re.compile(r'\bTQueue\s*<'), 'Containers/Queue.h'),

    # Strings / Names / Text
    (re.compile(r'\bFName\b'), 'UObject/NameTypes.h'),
    (re.compile(r'\bFText\b'), 'Internationalization/Text.h'),
    (re.compile(r'\bFStringView\b'), 'Containers/StringView.h'),

    # Math
    (re.compile(r'\bFVector\b(?!2D|4)'), 'Math/Vector.h'),
    (re.compile(r'\bFVector2D\b'), 'Math/Vector2D.h'),
    (re.compile(r'\bFVector4\b'), 'Math/Vector4.h'),
    (re.compile(r'\bFRotator\b'), 'Math/Rotator.h'),
    (re.compile(r'\bFTransform\b'), 'Math/Transform.h'),
    (re.compile(r'\bFQuat\b'), 'Math/Quat.h'),
    (re.compile(r'\bFMatrix\b'), 'Math/Matrix.h'),
    (re.compile(r'\bFColor\b'), 'Math/Color.h'),
    (re.compile(r'\bFLinearColor\b'), 'Math/Color.h'),
    (re.compile(r'\bFBox\b(?!2D)'), 'Math/Box.h'),
    (re.compile(r'\bFBox2D\b'), 'Math/Box2D.h'),
    (re.compile(r'\bFPlane\b'), 'Math/Plane.h'),
    (re.compile(r'\bFSphere\b'), 'Math/Sphere.h'),
    (re.compile(r'\bFMath\b'), 'Math/UnrealMathUtility.h'),
    (re.compile(r'\bFIntPoint\b'), 'Math/IntPoint.h'),
    (re.compile(r'\bFIntVector\b'), 'Math/IntVector.h'),
    (re.compile(r'\bFIntRect\b'), 'Math/IntRect.h'),
    (re.compile(r'\bFRay\b'), 'Math/Ray.h'),

    # Delegates
    (re.compile(r'\bDECLARE_DELEGATE\b'), 'Delegates/Delegate.h'),
    (re.compile(r'\bDECLARE_MULTICAST_DELEGATE\b'), 'Delegates/Delegate.h'),
    (re.compile(r'\bDECLARE_DYNAMIC_DELEGATE\b'), 'Delegates/Delegate.h'),
    (re.compile(r'\bDECLARE_DYNAMIC_MULTICAST_DELEGATE\b'), 'Delegates/Delegate.h'),
    (re.compile(r'\bDECLARE_EVENT\b'), 'Delegates/Delegate.h'),

    # Logging
    (re.compile(r'\bUE_LOG\b'), 'Logging/LogMacros.h'),
    (re.compile(r'\bDECLARE_LOG_CATEGORY\b'), 'Logging/LogMacros.h'),
    (re.compile(r'\bDEFINE_LOG_CATEGORY\b'), 'Logging/LogMacros.h'),

    # Smart pointers
    (re.compile(r'\bTSharedPtr\s*<'), 'Templates/SharedPointer.h'),
    (re.compile(r'\bTSharedRef\s*<'), 'Templates/SharedPointer.h'),
    (re.compile(r'\bTWeakPtr\s*<'), 'Templates/SharedPointer.h'),
    (re.compile(r'\bMakeShared\s*<'), 'Templates/SharedPointer.h'),
    (re.compile(r'\bMakeShareable\b'), 'Templates/SharedPointer.h'),
    (re.compile(r'\bTUniquePtr\s*<'), 'Templates/UniquePtr.h'),
    (re.compile(r'\bMakeUnique\s*<'), 'Templates/UniquePtr.h'),

    # UObject macros (if used in .h typically)
    (re.compile(r'\bUCLASS\s*\('), 'UObject/ObjectMacros.h'),
    (re.compile(r'\bUSTRUCT\s*\('), 'UObject/ObjectMacros.h'),
    (re.compile(r'\bUENUM\s*\('), 'UObject/ObjectMacros.h'),
    (re.compile(r'\bUPROPERTY\s*\('), 'UObject/ObjectMacros.h'),
    (re.compile(r'\bUFUNCTION\s*\('), 'UObject/ObjectMacros.h'),
    (re.compile(r'\bGENERATED_BODY\s*\('), 'UObject/ObjectMacros.h'),

    # Misc
    (re.compile(r'\bFPaths\b'), 'Misc/Paths.h'),
    (re.compile(r'\bFGuid\b'), 'Misc/Guid.h'),
    (re.compile(r'\bFDateTime\b'), 'Misc/DateTime.h'),
    (re.compile(r'\bFTimespan\b'), 'Misc/Timespan.h'),
    (re.compile(r'\bFFileHelper\b'), 'Misc/FileHelper.h'),
    (re.compile(r'\bTSubclassOf\s*<'), 'Templates/SubclassOf.h'),
    (re.compile(r'\bTSoftObjectPtr\s*<'), 'UObject/SoftObjectPtr.h'),
    (re.compile(r'\bTSoftClassPtr\s*<'), 'UObject/SoftObjectPtr.h'),
    (re.compile(r'\bTWeakObjectPtr\s*<'), 'UObject/WeakObjectPtrTemplates.h'),
    (re.compile(r'\bCast\s*<'), 'UObject/Object.h'),
    (re.compile(r'\bCastChecked\s*<'), 'UObject/Object.h'),
    (re.compile(r'\bNewObject\s*<'), 'UObject/Object.h'),
    (re.compile(r'\bIsValid\s*\('), 'UObject/Object.h'),
    (re.compile(r'\bFCriticalSection\b'), 'HAL/CriticalSection.h'),
    (re.compile(r'\bFScopeLock\b'), 'Misc/ScopeLock.h'),
    (re.compile(r'\bFPlatformProcess\b'), 'HAL/PlatformProcess.h'),
    (re.compile(r'\bFPlatformMisc\b'), 'HAL/PlatformMisc.h'),
    (re.compile(r'\bAsync\s*\('), 'Async/Async.h'),
    (re.compile(r'\bFAsyncTask\b'), 'Async/AsyncWork.h'),
    (re.compile(r'\bIFileManager\b'), 'HAL/FileManager.h'),
    (re.compile(r'\bFArchive\b'), 'Serialization/Archive.h'),

    # Engine objects (commonly appear alongside CoreMinimal)
    (re.compile(r'\bAActor\b'), 'GameFramework/Actor.h'),
    (re.compile(r'\bAPawn\b'), 'GameFramework/Pawn.h'),
    (re.compile(r'\bACharacter\b'), 'GameFramework/Character.h'),
    (re.compile(r'\bAPlayerController\b'), 'GameFramework/PlayerController.h'),
    (re.compile(r'\bAGameModeBase\b'), 'GameFramework/GameModeBase.h'),
    (re.compile(r'\bUActorComponent\b'), 'Components/ActorComponent.h'),
    (re.compile(r'\bUSceneComponent\b'), 'Components/SceneComponent.h'),
    (re.compile(r'\bUPrimitiveComponent\b'), 'Components/PrimitiveComponent.h'),
    (re.compile(r'\bUGameInstance\b'), 'Engine/GameInstance.h'),
    (re.compile(r'\bUWorld\b'), 'Engine/World.h'),
    (re.compile(r'\bUGameplayStatics\b'), 'Kismet/GameplayStatics.h'),
    (re.compile(r'\bGEngine\b'), 'Engine/Engine.h'),
    (re.compile(r'\bFTimerHandle\b'), 'Engine/EngineTypes.h'),
    (re.compile(r'\bFTimerManager\b'), 'Engine/World.h'),

    # Interfaces
    (re.compile(r'\bUIINTERFACE\b'), 'UObject/Interface.h'),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_source_dir(path: Path) -> Path | None:
    """Resolve the Source/ directory from a user-supplied path.

    Accepts:
        - ``*.uproject`` / ``*.uplugin`` → ``Source/`` next to it
        - A directory containing ``Source/``
        - A ``Source/`` directory itself
    """
    if path.is_file() and path.suffix in ('.uproject', '.uplugin'):
        candidate = path.parent / 'Source'
        return candidate if candidate.is_dir() else None
    if path.is_dir():
        if path.name == 'Source':
            return path
        candidate = path / 'Source'
        if candidate.is_dir():
            return candidate
    return None


def _walk_source_files(
    source_dir: Path,
    extensions: set[str] | None = None,
) -> list[Path]:
    """Collect source files using os.walk with pruning (no rglob)."""
    exts = extensions or _SOURCE_EXTENSIONS
    result: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(source_dir):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith('.')
        ]
        for fname in filenames:
            if Path(fname).suffix.lower() in exts:
                result.append(Path(dirpath) / fname)
    return result


def _read_text(path: Path) -> str | None:
    """Read a file as text, return None on failure."""
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None


def _find_paired_header(cpp_path: Path) -> Path | None:
    """Find the .h file paired with a .cpp file.

    Handles standard UE module layouts:
        - Same directory (flat layout)
        - Private/X.cpp → Public/X.h (split layout)
        - Private/Sub/X.cpp → Public/Sub/X.h (nested split layout)
    """
    stem = cpp_path.stem

    # 1. Same directory
    h_same = cpp_path.with_suffix('.h')
    if h_same.exists():
        return h_same

    # 2. Public/Private split: walk up to find a "Private" ancestor,
    #    then mirror the relative path into "Public".
    parts = cpp_path.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].lower() == 'private':
            public_dir = Path(*parts[:i]) / 'Public'
            # relative path from Private/ to the file (minus file itself)
            sub_parts = parts[i + 1: -1]
            if sub_parts:
                candidate = public_dir.joinpath(*sub_parts) / f'{stem}.h'
            else:
                candidate = public_dir / f'{stem}.h'
            if candidate.exists():
                return candidate
            # Also search recursively under Public/ for the header
            if public_dir.is_dir():
                for dirpath, _, filenames in os.walk(public_dir):
                    if f'{stem}.h' in filenames:
                        return Path(dirpath) / f'{stem}.h'
            break

    # 3. Broader search: go up to the module root (parent of Public/Private
    #    or parent of the .cpp file) and search for stem.h
    module_root = cpp_path.parent
    for i in range(len(parts) - 1, -1, -1):
        if parts[i].lower() in ('private', 'public', 'classes'):
            module_root = Path(*parts[:i]) if i > 0 else cpp_path.parent
            break

    if module_root.is_dir():
        for dirpath, dirnames, filenames in os.walk(module_root):
            dirnames[:] = [
                d for d in dirnames
                if d not in {'Binaries', 'Intermediate', 'DerivedDataCache'}
            ]
            if f'{stem}.h' in filenames:
                found = Path(dirpath) / f'{stem}.h'
                if found != h_same:  # already checked
                    return found

    return None


def _strip_comments(text: str) -> str:
    """Remove C/C++ comments for cleaner type detection."""
    # Remove block comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Remove line comments
    text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
    return text


def _strip_include_lines(text: str) -> str:
    """Remove #include lines so type detection doesn't match header paths."""
    return re.sub(r'^\s*#\s*include\s+.*$', '', text, flags=re.MULTILINE)


def _detect_needed_headers(content: str) -> set[str]:
    """Detect which specific headers are needed based on type usage."""
    # Work on content with comments and #include lines stripped
    clean = _strip_include_lines(_strip_comments(content))
    needed: set[str] = set()
    for pattern, header in _TYPE_HEADER_MAP:
        if pattern.search(clean):
            needed.add(header)
    return needed


def _get_existing_includes(content: str) -> list[str]:
    """Extract all quoted #include paths from content."""
    return _INCLUDE_RE.findall(content)


def _find_last_include_end(content: str) -> int | None:
    """Find the byte offset of the end of the last #include line."""
    last: re.Match[str] | None = None
    for m in _LAST_INCLUDE_RE.finditer(content):
        last = m
    if last is None:
        return None
    return last.end()


def _detect_engine_version(path: Path) -> tuple[int, int] | None:
    """Try to detect UE engine version from a .uproject file.

    Returns (major, minor) or None if undetermined.
    Searches for .uproject in the given path or its parents.
    """
    import json

    # Find .uproject file
    uproject: Path | None = None
    if path.is_file() and path.suffix == '.uproject':
        uproject = path
    elif path.is_file() and path.suffix == '.uplugin':
        # Walk up looking for a .uproject
        for parent in path.parent.parents:
            candidates = list(parent.glob('*.uproject'))
            if candidates:
                uproject = candidates[0]
                break
    elif path.is_dir():
        candidates = list(path.glob('*.uproject'))
        if candidates:
            uproject = candidates[0]
        else:
            for parent in path.parents:
                candidates = list(parent.glob('*.uproject'))
                if candidates:
                    uproject = candidates[0]
                    break

    if uproject is None:
        return None

    try:
        data = json.loads(uproject.read_text(encoding='utf-8'))
        assoc = data.get('EngineAssociation', '')
        # EngineAssociation is typically "5.4", "5.1", "4.27", etc.
        # Custom builds may use a GUID — skip those.
        m = re.match(r'^(\d+)\.(\d+)', str(assoc))
        if m:
            return int(m.group(1)), int(m.group(2))
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return None


def _supports_inline_generated(
    path: Path,
    source_files: list[Path],
) -> bool:
    """Check if the project supports UE_INLINE_GENERATED_CPP_BY_NAME.

    The macro was introduced in UE 5.1. Returns True if:
        - Engine version >= 5.1
        - Any existing file already uses the macro (custom engine builds)
        - Version is undetermined (assume modern engine)
    """
    version = _detect_engine_version(path)
    if version is not None:
        major, minor = version
        if major < 5 or (major == 5 and minor < 1):
            return False
        return True

    # Version unknown — check if any file already uses the macro
    # (sample up to 50 .cpp files to keep it fast)
    sample = [f for f in source_files if f.suffix.lower() == '.cpp'][:50]
    for fpath in sample:
        content = _read_text(fpath)
        if content and _INLINE_GENERATED_RE.search(content):
            return True

    # Unknown version, no existing usage — assume supported (modern default)
    return True


def _line_preprocessor_depths(content: str) -> list[int]:
    """Return preprocessor conditional nesting depth for each line.

    Depth 0 = top-level code (outside any ``#if`` / ``#ifdef`` / ``#ifndef``).
    Depth >= 1 = inside one or more conditional blocks.
    """
    lines = content.splitlines()
    depths: list[int] = []
    depth = 0
    for line in lines:
        stripped = line.strip()
        if _PP_ENDIF_RE.match(stripped):
            depth = max(0, depth - 1)
            depths.append(depth)
        elif _PP_IF_RE.match(stripped):
            depths.append(depth)
            depth += 1
        else:
            depths.append(depth)
    return depths


def _find_last_include_line_at_depth_zero(content: str) -> int | None:
    """Find the 1-based line number of the last ``#include`` at preprocessor depth 0.

    Returns None if no such include exists.
    """
    depths = _line_preprocessor_depths(content)
    lines = content.splitlines()
    last_line: int | None = None
    include_re = re.compile(r'^\s*#\s*include\s+')
    for i, line in enumerate(lines):
        if depths[i] == 0 and include_re.match(line):
            last_line = i + 1  # 1-based
    return last_line


def find_plugins(uproject_path: Path) -> list[PluginInfo]:
    """Discover plugins inside a UE project.

    Searches the ``Plugins/`` directory next to the ``.uproject`` file
    recursively for ``.uplugin`` files.
    """
    import json as _json

    plugins_dir = uproject_path.parent / 'Plugins'
    if not plugins_dir.is_dir():
        return []

    result: list[PluginInfo] = []
    for dirpath, dirnames, filenames in os.walk(plugins_dir):
        # Skip engine-standard junk directories
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith('.')
        ]
        for fname in filenames:
            if not fname.endswith('.uplugin'):
                continue
            uplugin_path = Path(dirpath) / fname
            name = uplugin_path.stem
            category = ""
            try:
                data = _json.loads(uplugin_path.read_text(encoding='utf-8'))
                category = data.get('Category', '')
            except (OSError, _json.JSONDecodeError, ValueError):
                pass

            source_dir = uplugin_path.parent / 'Source'
            result.append(PluginInfo(
                name=name,
                path=uplugin_path,
                category=category or "Uncategorized",
                source_dir=source_dir if source_dir.is_dir() else None,
            ))

    result.sort(key=lambda p: (p.category, p.name))
    return result


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

class IncludeAnalyzer:
    """Scans a UE Source directory and generates optimization change lists."""

    def __init__(
        self,
        *,
        progress_callback: ProgressCallback | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        self._progress = progress_callback
        self._log = log_callback

    def _emit_log(self, text: str, level: LogLevel = LogLevel.INFO) -> None:
        if self._log:
            self._log(LogMessage(text=text, level=level))

    def _emit_progress(self, value: int) -> None:
        if self._progress:
            self._progress(value)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preview(
        self,
        path: Path,
        scope: OptimizeScope,
    ) -> list[IncludeChange]:
        """Scan source tree and return proposed changes (dry run)."""
        source_dir = _find_source_dir(path)
        if source_dir is None:
            self._emit_log(f"Cannot find Source/ directory in {path}", LogLevel.ERROR)
            return []

        all_files = _walk_source_files(source_dir)

        # Discover plugins if .uproject and flag set
        plugin_file_lists: list[tuple[str, Path, list[Path]]] = []
        if (
            scope.include_plugins
            and path.is_file()
            and path.suffix == '.uproject'
        ):
            plugins = find_plugins(path)
            for pi in plugins:
                if pi.name in scope.excluded_plugins:
                    continue
                if pi.source_dir is None:
                    continue
                pfiles = _walk_source_files(pi.source_dir)
                if pfiles:
                    plugin_file_lists.append((pi.name, pi.source_dir, pfiles))

        total_files = len(all_files)
        for _, _, pf in plugin_file_lists:
            total_files += len(pf)

        if total_files == 0:
            self._emit_log("No source files found", LogLevel.WARNING)
            return []

        self._emit_log(f"Scanning {total_files} files")
        changes: list[IncludeChange] = []

        # Check engine version compatibility for UE_INLINE_GENERATED_CPP_BY_NAME
        do_inline = scope.add_inline_generated
        if do_inline:
            if not _supports_inline_generated(path, all_files):
                version = _detect_engine_version(path)
                ver_str = f"{version[0]}.{version[1]}" if version else "unknown"
                self._emit_log(
                    f"UE_INLINE_GENERATED_CPP_BY_NAME not supported "
                    f"(engine {ver_str}, requires 5.1+) — skipping",
                    LogLevel.WARNING,
                )
                do_inline = False

        scanned = 0

        # Scan project source
        for fpath in all_files:
            rel = str(fpath.relative_to(source_dir.parent))
            file_changes = self._scan_file(fpath, rel, source_dir, scope, do_inline)
            for c in file_changes:
                c.source_label = ""
            changes.extend(file_changes)
            scanned += 1
            if total_files > 0:
                self._emit_progress(int(scanned / total_files * 100))

        # Scan plugins
        for plugin_name, plugin_src, plugin_files in plugin_file_lists:
            for fpath in plugin_files:
                rel = str(fpath.relative_to(plugin_src.parent))
                file_changes = self._scan_file(
                    fpath, rel, plugin_src, scope, do_inline,
                )
                for c in file_changes:
                    c.source_label = plugin_name
                changes.extend(file_changes)
                scanned += 1
                if total_files > 0:
                    self._emit_progress(int(scanned / total_files * 100))

        self._emit_log(f"Found {len(changes)} optimizations across {total_files} files")
        return changes

    def _scan_file(
        self,
        fpath: Path,
        rel: str,
        source_dir: Path,
        scope: OptimizeScope,
        do_inline: bool,
    ) -> list[IncludeChange]:
        """Scan a single file for all enabled optimizations."""
        content = _read_text(fpath)
        if content is None:
            return []

        changes: list[IncludeChange] = []

        if do_inline:
            changes.extend(
                self._check_inline_generated(fpath, rel, content, source_dir),
            )

        if scope.replace_coreminimal:
            changes.extend(self._check_coreminimal(fpath, rel, content))

        if scope.remove_duplicates:
            changes.extend(self._check_duplicates(rel, content))

        if scope.fix_preprocessor_includes:
            changes.extend(self._check_preprocessor_issues(rel, content))

        return changes

    def execute(
        self,
        path: Path,
        scope: OptimizeScope,
    ) -> OptimizeResult:
        """Apply optimizations to files on disk."""
        t0 = time.monotonic()
        source_dir = _find_source_dir(path)
        if source_dir is None:
            return OptimizeResult(
                status=OptimizeStatus.FAILED,
                message=f"Cannot find Source/ directory in {path}",
            )

        # Backup
        backup_path: Path | None = None
        if scope.create_backup:
            backup_path = source_dir.parent / f"{source_dir.name}_backup"
            try:
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                shutil.copytree(source_dir, backup_path)
                self._emit_log(f"Backup created: {backup_path}", LogLevel.SUCCESS)
            except OSError as e:
                return OptimizeResult(
                    status=OptimizeStatus.FAILED,
                    message=f"Backup failed: {e}",
                )

            # Backup plugins too
            if (
                scope.include_plugins
                and path.is_file()
                and path.suffix == '.uproject'
            ):
                plugins = find_plugins(path)
                for pi in plugins:
                    if pi.name in scope.excluded_plugins:
                        continue
                    if pi.source_dir is None or not pi.source_dir.is_dir():
                        continue
                    pb = pi.source_dir.parent / f"{pi.source_dir.name}_backup"
                    try:
                        if pb.exists():
                            shutil.rmtree(pb)
                        shutil.copytree(pi.source_dir, pb)
                        self._emit_log(
                            f"Plugin backup: {pi.name}", LogLevel.SUCCESS,
                        )
                    except OSError as e:
                        self._emit_log(
                            f"Plugin backup failed ({pi.name}): {e}",
                            LogLevel.WARNING,
                        )

        changes = self.preview(path, scope)
        if not changes:
            return OptimizeResult(
                status=OptimizeStatus.SUCCESS,
                message="No optimizations needed",
                duration_seconds=time.monotonic() - t0,
            )

        # Build base dir mapping for resolving rel_path → abs_path
        # "" (project) → source_dir.parent, plugin_name → plugin source parent
        base_dirs: dict[str, Path] = {"": source_dir.parent}
        if (
            scope.include_plugins
            and path.is_file()
            and path.suffix == '.uproject'
        ):
            for pi in find_plugins(path):
                if pi.source_dir is not None:
                    base_dirs[pi.name] = pi.source_dir.parent

        # Group changes by (source_label, file_path)
        by_file: dict[tuple[str, str], list[IncludeChange]] = {}
        for c in changes:
            by_file.setdefault((c.source_label, c.file_path), []).append(c)

        applied = 0
        errors: list[str] = []
        files_modified = 0

        for (src_label, rel_path), file_changes in by_file.items():
            base = base_dirs.get(src_label, source_dir.parent)
            abs_path = base / rel_path
            content = _read_text(abs_path)
            if content is None:
                errors.append(f"Cannot read {rel_path}")
                continue

            new_content = self._apply_changes(content, file_changes)
            if new_content == content:
                continue

            try:
                abs_path.write_text(new_content, encoding='utf-8')
                files_modified += 1
                applied += len(file_changes)
                label = f"[{src_label}] " if src_label else ""
                self._emit_log(
                    f"Modified {label}{rel_path} ({len(file_changes)} changes)",
                    LogLevel.SUCCESS,
                )
            except OSError as e:
                errors.append(f"Write error {rel_path}: {e}")
                self._emit_log(f"Failed to write {rel_path}: {e}", LogLevel.ERROR)

        duration = time.monotonic() - t0
        status = OptimizeStatus.SUCCESS if not errors else OptimizeStatus.FAILED
        return OptimizeResult(
            status=status,
            message=f"Applied {applied} optimizations to {files_modified} files",
            changes_applied=applied,
            files_modified=files_modified,
            duration_seconds=duration,
            errors=errors,
            backup_path=backup_path,
        )

    # ------------------------------------------------------------------
    # Analysis: UE_INLINE_GENERATED_CPP_BY_NAME
    # ------------------------------------------------------------------

    def _check_inline_generated(
        self,
        fpath: Path,
        rel: str,
        content: str,
        source_dir: Path,
    ) -> list[IncludeChange]:
        """Check if a .cpp file needs UE_INLINE_GENERATED_CPP_BY_NAME."""
        if fpath.suffix.lower() != '.cpp':
            return []

        # Already has the macro
        if _INLINE_GENERATED_RE.search(content):
            return []

        # Check if paired .h has GENERATED_BODY()
        header = _find_paired_header(fpath)
        if header is None:
            return []
        h_content = _read_text(header)
        if h_content is None or not _GENERATED_BODY_RE.search(h_content):
            return []

        # Find insertion point: after last #include at depth 0
        # (avoids inserting inside #if WITH_EDITOR / etc.)
        line_no = _find_last_include_line_at_depth_zero(content)
        if line_no is None:
            # Fallback: after last #include of any depth
            insert_pos = _find_last_include_end(content)
            if insert_pos is None:
                return []
            line_no = content[:insert_pos].count('\n') + 1

        stem = fpath.stem

        return [IncludeChange(
            change_type=ChangeType.ADD_INLINE_GENERATED,
            category="UE_INLINE_GENERATED_CPP_BY_NAME",
            file_path=rel,
            old_value=f"(after last #include, line {line_no})",
            new_value=f'#include UE_INLINE_GENERATED_CPP_BY_NAME({stem})',
            line_number=line_no,
        )]

    # ------------------------------------------------------------------
    # Analysis: CoreMinimal.h replacement
    # ------------------------------------------------------------------

    def _check_coreminimal(
        self,
        fpath: Path,
        rel: str,
        content: str,
    ) -> list[IncludeChange]:
        """Check if CoreMinimal.h can be replaced with specific headers."""
        if not _COREMINIMAL_RE.search(content):
            return []

        needed = _detect_needed_headers(content)
        # Always include CoreTypes.h as the safe baseline
        needed.add('CoreTypes.h')
        # Sort for deterministic output
        sorted_headers = sorted(needed)

        existing = set(_get_existing_includes(content))
        # Don't add headers that are already explicitly included
        to_add = [h for h in sorted_headers if h not in existing]

        new_includes = '\n'.join(f'#include "{h}"' for h in to_add)
        old_line = '#include "CoreMinimal.h"'

        return [IncludeChange(
            change_type=ChangeType.REPLACE_COREMINIMAL,
            category="CoreMinimal Replacement",
            file_path=rel,
            old_value=old_line,
            new_value=new_includes,
            line_number=self._find_line_number(content, 'CoreMinimal.h'),
        )]

    # ------------------------------------------------------------------
    # Analysis: duplicate includes
    # ------------------------------------------------------------------

    def _check_duplicates(
        self,
        rel: str,
        content: str,
    ) -> list[IncludeChange]:
        """Find duplicate #include lines."""
        seen: dict[str, int] = {}
        changes: list[IncludeChange] = []

        for line_no, line in enumerate(content.splitlines(), 1):
            m = re.match(r'^\s*#\s*include\s+([<"][^>"]+[>"])', line)
            if m is None:
                continue
            include_path = m.group(1)
            if include_path in seen:
                changes.append(IncludeChange(
                    change_type=ChangeType.REMOVE_DUPLICATE,
                    category="Duplicate Includes",
                    file_path=rel,
                    old_value=line.strip(),
                    new_value="(removed — first occurrence at line "
                              f"{seen[include_path]})",
                    line_number=line_no,
                ))
            else:
                seen[include_path] = line_no

        return changes

    # ------------------------------------------------------------------
    # Analysis: preprocessor block issues
    # ------------------------------------------------------------------

    def _check_preprocessor_issues(
        self,
        rel: str,
        content: str,
    ) -> list[IncludeChange]:
        """Find includes incorrectly placed inside preprocessor blocks.

        Detects ``UE_INLINE_GENERATED_CPP_BY_NAME`` macros that are inside
        ``#if`` / ``#ifdef`` / ``#ifndef`` blocks and proposes moving them
        to the top-level scope (after the enclosing ``#endif``).
        """
        lines = content.splitlines()
        depths = _line_preprocessor_depths(content)
        changes: list[IncludeChange] = []

        inline_re = re.compile(
            r'^\s*#\s*include\s+UE_INLINE_GENERATED_CPP_BY_NAME\s*\((.+?)\)',
        )

        for i, line in enumerate(lines):
            if depths[i] == 0:
                continue
            m = inline_re.match(line)
            if m is None:
                continue

            # Find the closing #endif for this nesting level
            target_depth = depths[i]
            endif_line = None
            for j in range(i + 1, len(lines)):
                if _PP_ENDIF_RE.match(lines[j].strip()) and depths[j] < target_depth:
                    endif_line = j + 1  # 1-based
                    break

            if endif_line is None:
                endif_line = len(lines)

            changes.append(IncludeChange(
                change_type=ChangeType.FIX_PREPROCESSOR_INCLUDE,
                category="Preprocessor Block Fix",
                file_path=rel,
                old_value=line.strip(),
                new_value=f"(move to line {endif_line + 1}, outside #if block)",
                line_number=i + 1,  # 1-based
            ))

        return changes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_line_number(content: str, needle: str) -> int:
        """Find the 1-based line number of the first occurrence of needle."""
        idx = content.find(needle)
        if idx < 0:
            return 0
        return content[:idx].count('\n') + 1

    # ------------------------------------------------------------------
    # Apply changes to content
    # ------------------------------------------------------------------

    def _apply_changes(
        self,
        content: str,
        changes: list[IncludeChange],
    ) -> str:
        """Apply a list of changes to file content and return modified text."""
        lines = content.splitlines(keepends=True)

        # Collect line indices to remove (0-based)
        remove_lines: set[int] = set()
        insert_after: dict[int, str] = {}   # line_idx → text to insert after
        replace_line: dict[int, str] = {}   # line_idx → replacement text
        # FIX_PREPROCESSOR_INCLUDE: remove from old position, insert after target
        pp_moves: list[tuple[int, int, str]] = []  # (from_idx, after_idx, text)

        for c in changes:
            idx = c.line_number - 1  # 0-based

            if c.change_type == ChangeType.REMOVE_DUPLICATE:
                if 0 <= idx < len(lines):
                    remove_lines.add(idx)

            elif c.change_type == ChangeType.ADD_INLINE_GENERATED:
                # Insert after the last #include line (line_number points there)
                if 0 <= idx < len(lines):
                    insert_after[idx] = c.new_value + '\n'

            elif c.change_type == ChangeType.REPLACE_COREMINIMAL:
                if 0 <= idx < len(lines):
                    replace_line[idx] = c.new_value + '\n'

            elif c.change_type == ChangeType.FIX_PREPROCESSOR_INCLUDE:
                if 0 <= idx < len(lines):
                    # Parse target line from new_value
                    m = re.search(r'line (\d+)', c.new_value)
                    if m:
                        target = int(m.group(1)) - 1  # 0-based
                    else:
                        target = len(lines) - 1
                    text = lines[idx].rstrip('\n\r')
                    pp_moves.append((idx, target, text))

        # Apply preprocessor moves
        for from_idx, after_idx, text in pp_moves:
            remove_lines.add(from_idx)
            # Accumulate if multiple inserts at same position
            existing = insert_after.get(after_idx, '')
            insert_after[after_idx] = existing + text + '\n'

        # Build new content
        result: list[str] = []
        for i, line in enumerate(lines):
            if i in remove_lines:
                continue
            if i in replace_line:
                result.append(replace_line[i])
            else:
                result.append(line)
            if i in insert_after:
                # Ensure current line ends with newline before appending
                if result and not result[-1].endswith('\n'):
                    result[-1] += '\n'
                result.append(insert_after[i])

        return ''.join(result)