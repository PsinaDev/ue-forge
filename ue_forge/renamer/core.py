"""
Core renaming engine for Unreal Engine plugins and projects.

Operates without Qt dependencies. Uses callbacks for progress reporting.
Supports dry-run (preview) and full execution modes.
"""
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Callable, Dict, Set

from framekit.types import LogLevel, LogMessage


LogCallback = Callable[[LogMessage], None]


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class RenameStatus(Enum):
    """Status of a rename operation."""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ChangeType(Enum):
    """Type of a single rename change."""
    RENAME_FOLDER = "rename_folder"
    RENAME_FILE = "rename_file"
    CONTENT_REPLACE = "content_replace"


@dataclass
class RenameChange:
    """A single atomic change in a rename operation."""
    change_type: ChangeType
    category: str
    file_path: str          # relative to root
    old_value: str
    new_value: str
    line_number: int = 0    # for content changes, 0 = not applicable

    @property
    def is_file_op(self) -> bool:
        return self.change_type in (ChangeType.RENAME_FILE, ChangeType.RENAME_FOLDER)


@dataclass
class RenameScope:
    """Controls which parts of the rename are executed."""
    rename_modules: bool = True
    rename_api_macros: bool = True
    rename_includes: bool = True
    rename_build_cs: bool = True
    rename_module_macros: bool = True
    rename_comments: bool = True
    create_backup: bool = True


@dataclass
class RenameResult:
    """Result of a rename operation."""
    status: RenameStatus
    message: str
    changes_applied: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    backup_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOURCE_EXTENSIONS = {".h", ".hpp", ".cpp", ".c", ".cc", ".inl", ".cs", ".py"}
_CONFIG_EXTENSIONS = {".ini", ".cfg"}

_BINARY_EXTENSIONS = {
    ".uasset", ".umap", ".dll", ".so", ".dylib", ".exe", ".pdb",
    ".png", ".jpg", ".jpeg", ".bmp", ".tga", ".exr", ".ico",
    ".ttf", ".otf", ".wav", ".ogg", ".mp3", ".mp4",
    ".zip", ".pak", ".ucas", ".utoc",
}


def _is_text_file(path: Path) -> bool:
    """Check if a file is likely a text file worth scanning."""
    if path.suffix.lower() in _BINARY_EXTENSIONS:
        return False
    if path.suffix.lower() in _SOURCE_EXTENSIONS | _CONFIG_EXTENSIONS | {".uplugin", ".uproject", ".json", ".xml", ".md", ".txt", ".yaml", ".yml"}:
        return True
    # For unknown extensions, try reading a small chunk
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
            return b"\x00" not in chunk
    except (OSError, PermissionError):
        return False


def _read_text(path: Path) -> Optional[str]:
    """Read a text file, handling BOM."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
        except OSError:
            return None
    return None


def _write_text(path: Path, content: str) -> None:
    """Write text file preserving utf-8."""
    path.write_text(content, encoding="utf-8")


def _safe_rename(src: Path, dst: Path) -> None:
    """Rename a file or directory, handling cross-device moves."""
    if dst.exists():
        raise FileExistsError(f"Target already exists: {dst}")
    try:
        src.rename(dst)
    except OSError:
        # Cross-device fallback
        if src.is_dir():
            shutil.copytree(src, dst)
            shutil.rmtree(src)
        else:
            shutil.copy2(src, dst)
            src.unlink()


_SKIP_DIRS = frozenset({
    "Binaries", "Intermediate", "DerivedDataCache", "Saved",
    ".vs", ".idea", "__pycache__", "node_modules", ".git",
})

ProgressCallback = Callable[[int], None]


def _walk_files(root: Path, extensions: Optional[Set[str]] = None) -> List[Path]:
    """Walk files under root, skipping heavy UE dirs. Iterative, no rglob."""
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fname in filenames:
            if extensions is None or Path(fname).suffix.lower() in extensions:
                result.append(Path(dirpath) / fname)
    return result


def _walk_dirs(root: Path) -> List[Path]:
    """Walk directories under root, skipping heavy UE dirs. Iterative, no rglob."""
    result = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for d in dirnames:
            result.append(Path(dirpath) / d)
    return result


# ---------------------------------------------------------------------------
# PluginRenamer
# ---------------------------------------------------------------------------

class PluginRenamer:
    """
    Renames an Unreal Engine plugin: folders, files, source code, macros,
    includes, .uplugin contents, and module references.

    Usage:
        renamer = PluginRenamer(log_callback=print_log)
        changes = renamer.preview(uplugin_path, "OldName", "NewName", scope)
        result  = renamer.execute(uplugin_path, "OldName", "NewName", scope)
    """

    def __init__(self, log_callback: Optional[LogCallback] = None, progress_callback: Optional[ProgressCallback] = None):
        self._log_callback = log_callback
        self._progress_callback = progress_callback

    def set_log_callback(self, callback: LogCallback) -> None:
        self._log_callback = callback

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        self._progress_callback = callback

    def _log(self, text: str, level: LogLevel = LogLevel.INFO) -> None:
        if self._log_callback:
            self._log_callback(LogMessage(text=text, level=level))

    def _progress(self, value: int) -> None:
        if self._progress_callback:
            self._progress_callback(min(100, max(0, value)))

    # ------------------------------------------------------------------
    # Preview (dry-run)
    # ------------------------------------------------------------------

    def preview(
        self,
        uplugin_path: Path,
        old_name: str,
        new_name: str,
        scope: Optional[RenameScope] = None,
    ) -> List[RenameChange]:
        """
        Generate a list of all changes that would be made.
        Does NOT modify any files.
        """
        if scope is None:
            scope = RenameScope()

        uplugin_path = Path(uplugin_path).resolve()
        if not uplugin_path.exists() or uplugin_path.suffix != ".uplugin":
            return []

        plugin_dir = uplugin_path.parent
        changes: List[RenameChange] = []

        modules = self._parse_modules(uplugin_path)
        self._progress(5)

        # 1) File system: full path renames
        changes.extend(self._preview_filesystem(plugin_dir, old_name, new_name))
        self._progress(15)

        # 2) .uplugin JSON contents
        changes.extend(self._preview_uplugin_contents(uplugin_path, old_name, new_name, modules))
        self._progress(20)

        # 3) Per-module changes (content only, folders already in File System)
        if scope.rename_modules:
            n = max(len(modules), 1)
            for i, mod in enumerate(modules):
                changes.extend(self._preview_module(plugin_dir, mod, old_name, new_name, scope))
                self._progress(20 + int(15 * (i + 1) / n))

        # 4) Global source scan — bulk of work, gets per-file progress
        source_dir = plugin_dir / "Source"
        if source_dir.exists():
            changes.extend(self._preview_source_scan(
                source_dir, old_name, new_name, scope, progress_range=(35, 95),
            ))

        self._progress(100)
        return changes

    def _parse_modules(self, uplugin_path: Path) -> List[Dict]:
        """Parse module list from .uplugin file."""
        try:
            text = _read_text(uplugin_path)
            if not text:
                return []
            data = json.loads(text)
            return data.get("Modules", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _preview_uplugin_contents(
        self,
        uplugin_path: Path,
        old_name: str,
        new_name: str,
        modules: List[Dict],
    ) -> List[RenameChange]:
        """Preview changes inside .uplugin JSON."""
        changes = []
        text = _read_text(uplugin_path) or ""

        # FriendlyName
        if f'"FriendlyName"' in text:
            # Match old name as FriendlyName value
            if re.search(rf'"FriendlyName"\s*:\s*"[^"]*{re.escape(old_name)}[^"]*"', text):
                changes.append(RenameChange(
                    change_type=ChangeType.CONTENT_REPLACE,
                    category=".uplugin Contents",
                    file_path=uplugin_path.name,
                    old_value=f'"FriendlyName": "...{old_name}..."',
                    new_value=f'"FriendlyName": "...{new_name}..."',
                ))

        # Module name entries
        for mod in modules:
            mod_name = mod.get("Name", "")
            if old_name in mod_name:
                new_mod = mod_name.replace(old_name, new_name)
                changes.append(RenameChange(
                    change_type=ChangeType.CONTENT_REPLACE,
                    category=".uplugin Contents",
                    file_path=uplugin_path.name,
                    old_value=f'"Name": "{mod_name}"',
                    new_value=f'"Name": "{new_mod}"',
                ))

        return changes

    def _preview_filesystem(
        self,
        root_dir: Path,
        old_name: str,
        new_name: str,
    ) -> List[RenameChange]:
        """
        Preview all directory and file paths that contain old_name in their name.
        Shows FULL relative paths with ALL occurrences replaced.
        Skips Binaries/Intermediate/etc. entirely (does not traverse them).
        """
        changes = []
        root_parent = root_dir.parent
        _skip_dirs = {"Binaries", "Intermediate", "DerivedDataCache", "Saved", ".vs", ".idea", "__pycache__", "node_modules"}

        # Root folder itself
        if old_name in root_dir.name:
            old_root = root_dir.name
            new_root = old_root.replace(old_name, new_name)
            changes.append(RenameChange(
                change_type=ChangeType.RENAME_FOLDER,
                category="File System",
                file_path=old_root,
                old_value=old_root + "/",
                new_value=new_root + "/",
            ))

        # Walk with pruning — os.walk lets us modify dirs in-place to skip subtrees
        all_dirs = []
        all_files = []
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Prune heavy directories — modifying dirnames in-place prevents os.walk from descending
            dirnames[:] = [d for d in dirnames if d not in _skip_dirs]

            dp = Path(dirpath)
            if old_name in dp.name:
                all_dirs.append(dp)

            for fname in filenames:
                if old_name in fname:
                    all_files.append(dp / fname)

        # Sort by depth for readability
        all_dirs.sort(key=lambda p: len(p.parts))
        all_files.sort(key=lambda p: len(p.parts))

        for p in all_dirs:
            rel = str(p.relative_to(root_parent))
            new_path = rel.replace(old_name, new_name)
            if new_path != rel:
                changes.append(RenameChange(
                    change_type=ChangeType.RENAME_FOLDER,
                    category="File System",
                    file_path=rel,
                    old_value=rel + "/",
                    new_value=new_path + "/",
                ))

        for p in all_files:
            rel = str(p.relative_to(root_parent))
            new_path = rel.replace(old_name, new_name)
            if new_path != rel:
                changes.append(RenameChange(
                    change_type=ChangeType.RENAME_FILE,
                    category="File System",
                    file_path=rel,
                    old_value=rel,
                    new_value=new_path,
                ))

        return changes

    def _preview_module(
        self,
        plugin_dir: Path,
        module: Dict,
        old_name: str,
        new_name: str,
        scope: RenameScope,
    ) -> List[RenameChange]:
        """Preview content changes for a single module (file/folder renames are in File System)."""
        changes = []
        mod_name = module.get("Name", "")
        mod_type = module.get("Type", "Runtime")
        new_mod_name = mod_name.replace(old_name, new_name) if old_name in mod_name else mod_name
        category = f"Module: {mod_name} ({mod_type})"

        source_dir = plugin_dir / "Source"
        mod_folder = source_dir / mod_name

        scan_folder = mod_folder if mod_folder.exists() else None
        if scan_folder is None:
            return changes

        # .Build.cs: class name + constructor
        if scope.rename_build_cs:
            build_cs = scan_folder / f"{mod_name}.Build.cs"
            if not build_cs.exists():
                build_cs = source_dir / f"{mod_name}.Build.cs"

            if build_cs.exists() and old_name in mod_name:
                text = _read_text(build_cs) or ""
                if f"class {mod_name}" in text:
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category=category,
                        file_path=f"{new_mod_name}.Build.cs",
                        old_value=f"class {mod_name} : ModuleRules",
                        new_value=f"class {new_mod_name} : ModuleRules",
                    ))
                # Constructor: public OldName(ReadOnlyTargetRules Target)
                ctor_pattern = rf'public\s+{re.escape(mod_name)}\s*\('
                if re.search(ctor_pattern, text):
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category=category,
                        file_path=f"{new_mod_name}.Build.cs",
                        old_value=f"public {mod_name}(ReadOnlyTargetRules Target)",
                        new_value=f"public {new_mod_name}(ReadOnlyTargetRules Target)",
                    ))

        # IMPLEMENT_MODULE / IMPLEMENT_GAME_MODULE
        if scope.rename_module_macros:
            for cpp_file in _walk_files(scan_folder, {".cpp"}):
                text = _read_text(cpp_file) or ""
                pattern = rf'IMPLEMENT_\w*MODULE\s*\([^)]*{re.escape(old_name)}[^)]*\)'
                for match in re.finditer(pattern, text):
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category=category,
                        file_path=str(cpp_file.relative_to(plugin_dir)),
                        old_value=match.group(0),
                        new_value=match.group(0).replace(old_name, new_name),
                    ))

        return changes

    def _preview_source_scan(
        self,
        source_dir: Path,
        old_name: str,
        new_name: str,
        scope: RenameScope,
        progress_range: tuple[int, int] = (40, 95),
    ) -> List[RenameChange]:
        """Scan all source files for API macros, includes, and comments.

        Reports per-file progress within *progress_range*.
        """
        changes: List[RenameChange] = []
        plugin_dir = source_dir.parent
        old_upper = old_name.upper()
        new_upper = new_name.upper()

        source_files = _walk_files(source_dir, _SOURCE_EXTENSIONS)
        total = max(len(source_files), 1)
        p_start, p_end = progress_range

        for idx, file_path in enumerate(source_files):
            if idx % 5 == 0:
                self._progress(p_start + int((p_end - p_start) * idx / total))

            text = _read_text(file_path)
            if text is None:
                continue

            # Fast skip: neither variant present in file
            if old_name not in text and old_upper not in text:
                continue

            rel = str(file_path.relative_to(plugin_dir))

            # API macros: OLDNAME_API — one entry per file (execute does global replace)
            if scope.rename_api_macros and old_upper in text:
                api_pattern = rf'\b{re.escape(old_upper)}_API\b'
                if re.search(api_pattern, text):
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category="API Macros",
                        file_path=rel,
                        old_value=f"{old_upper}_API",
                        new_value=f"{new_upper}_API",
                    ))

            # Include paths — each distinct #include line
            if scope.rename_includes and old_name in text:
                inc_pattern = rf'#include\s+"[^"]*{re.escape(old_name)}[^"]*"'
                seen_includes: Set[str] = set()
                for match in re.finditer(inc_pattern, text):
                    val = match.group(0)
                    if val not in seen_includes:
                        seen_includes.add(val)
                        changes.append(RenameChange(
                            change_type=ChangeType.CONTENT_REPLACE,
                            category="Include Paths",
                            file_path=rel,
                            old_value=val,
                            new_value=val.replace(old_name, new_name),
                        ))

            # Module macros: IMPLEMENT_MODULE, F*Module, Log categories
            if scope.rename_module_macros and old_name in text:
                # Log categories: LogOldName -> LogNewName
                log_pattern = rf'\bLog{re.escape(old_name)}\b'
                if re.search(log_pattern, text):
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category="Module Macros",
                        file_path=rel,
                        old_value=f"Log{old_name}",
                        new_value=f"Log{new_name}",
                    ))

            # .cs files: full identifier replacement (class names, strings, etc.)
            if scope.rename_build_cs and file_path.suffix == ".cs" and old_name in text:
                # Count all occurrences beyond what module preview already covers
                occurrences = text.count(old_name)
                if occurrences > 0:
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category="C# Source",
                        file_path=rel,
                        old_value=f"{old_name} ({occurrences} occurrences)",
                        new_value=f"{new_name}",
                    ))

            # Comments — line comments + block comments
            if scope.rename_comments and old_name in text:
                has_line = bool(re.search(rf'//[^\n]*\b{re.escape(old_name)}\b', text))
                has_block = bool(re.search(rf'/\*[\s\S]*?\b{re.escape(old_name)}\b[\s\S]*?\*/', text))
                if has_line or has_block:
                    label = []
                    if has_line:
                        label.append("//")
                    if has_block:
                        label.append("/* */")
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category="Comments",
                        file_path=rel,
                        old_value=f"{' + '.join(label)} ...{old_name}...",
                        new_value=f"{' + '.join(label)} ...{new_name}...",
                    ))

        self._progress(p_end)
        return changes

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(
        self,
        uplugin_path: Path,
        old_name: str,
        new_name: str,
        scope: Optional[RenameScope] = None,
    ) -> RenameResult:
        """
        Execute a full plugin rename.

        Renames are applied bottom-up: content changes first, then file renames,
        then folder renames (deepest first).
        """
        if scope is None:
            scope = RenameScope()

        start_time = time.time()
        uplugin_path = Path(uplugin_path).resolve()
        plugin_dir = uplugin_path.parent
        errors: List[str] = []
        changes_applied = 0
        backup_path = None

        # Validation
        if not uplugin_path.exists():
            return RenameResult(RenameStatus.FAILED, f"File not found: {uplugin_path}")
        if not re.match(r'^[A-Za-z][A-Za-z0-9]*$', new_name):
            return RenameResult(RenameStatus.FAILED, f"Invalid name: {new_name}")
        if old_name == new_name:
            return RenameResult(RenameStatus.FAILED, "Old and new names are identical")

        # Backup
        if scope.create_backup:
            backup_path = plugin_dir.parent / f"{plugin_dir.name}_backup_{int(time.time())}"
            self._log(f"Creating backup: {backup_path}", LogLevel.INFO)
            try:
                shutil.copytree(plugin_dir, backup_path)
            except (OSError, shutil.Error) as e:
                return RenameResult(RenameStatus.FAILED, f"Backup failed: {e}")

        try:
            # Phase 1: Content replacements in all text files
            self._log("Phase 1: Replacing content in source files...", LogLevel.INFO)
            count, errs = self._execute_content_replacements(plugin_dir, old_name, new_name, scope)
            changes_applied += count
            errors.extend(errs)

            # Phase 2: Rename files (deepest first)
            self._log("Phase 2: Renaming files...", LogLevel.INFO)
            count, errs = self._execute_file_renames(plugin_dir, old_name, new_name, scope)
            changes_applied += count
            errors.extend(errs)

            # Phase 3: Rename folders (deepest first)
            self._log("Phase 3: Renaming folders...", LogLevel.INFO)
            count, errs = self._execute_folder_renames(plugin_dir, old_name, new_name)
            changes_applied += count
            errors.extend(errs)

            # Phase 4: Rename plugin root folder
            if plugin_dir.name == old_name:
                new_plugin_dir = plugin_dir.parent / new_name
                self._log(f"Renaming plugin root: {plugin_dir.name} -> {new_name}", LogLevel.INFO)
                try:
                    _safe_rename(plugin_dir, new_plugin_dir)
                    changes_applied += 1
                except (OSError, FileExistsError) as e:
                    errors.append(f"Failed to rename root folder: {e}")

        except Exception as e:
            self._log(f"Rename failed: {e}", LogLevel.ERROR)
            return RenameResult(
                status=RenameStatus.FAILED,
                message=str(e),
                changes_applied=changes_applied,
                duration_seconds=time.time() - start_time,
                errors=errors,
                backup_path=backup_path,
            )

        duration = time.time() - start_time
        if errors:
            self._log(f"Completed with {len(errors)} errors", LogLevel.WARNING)
        else:
            self._log(f"Rename complete: {changes_applied} changes in {duration:.1f}s", LogLevel.SUCCESS)

        return RenameResult(
            status=RenameStatus.SUCCESS if not errors else RenameStatus.FAILED,
            message=f"Applied {changes_applied} changes" + (f" ({len(errors)} errors)" if errors else ""),
            changes_applied=changes_applied,
            duration_seconds=duration,
            errors=errors,
            backup_path=backup_path,
        )

    def _execute_content_replacements(
        self,
        root: Path,
        old_name: str,
        new_name: str,
        scope: RenameScope,
    ) -> tuple:
        """Replace old name in file contents. Returns (count, errors)."""
        count = 0
        errors = []
        old_upper = old_name.upper()
        new_upper = new_name.upper()

        # .uplugin file
        for uplugin in root.glob("*.uplugin"):
            try:
                text = _read_text(uplugin)
                if text and old_name in text:
                    data = json.loads(text)
                    changed = False

                    # FriendlyName
                    if "FriendlyName" in data and old_name in data["FriendlyName"]:
                        data["FriendlyName"] = data["FriendlyName"].replace(old_name, new_name)
                        changed = True

                    # Module names
                    for mod in data.get("Modules", []):
                        if old_name in mod.get("Name", ""):
                            mod["Name"] = mod["Name"].replace(old_name, new_name)
                            changed = True

                    if changed:
                        _write_text(uplugin, json.dumps(data, indent="\t", ensure_ascii=False))
                        count += 1
                        self._log(f"  Updated: {uplugin.name}", LogLevel.INFO)
            except Exception as e:
                errors.append(f"Failed to update {uplugin}: {e}")

        # Source files
        source_dir = root / "Source"
        if not source_dir.exists():
            return count, errors

        for file_path in _walk_files(source_dir):
            if not _is_text_file(file_path):
                continue

            try:
                text = _read_text(file_path)
                if text is None:
                    continue
                # Fast skip: neither variant present
                if old_name not in text and old_upper not in text:
                    continue
                original = text

                # API macros
                if scope.rename_api_macros:
                    text = re.sub(
                        rf'\b{re.escape(old_upper)}_API\b',
                        f'{new_upper}_API',
                        text,
                    )

                # Include paths
                if scope.rename_includes:
                    text = re.sub(
                        rf'(#include\s+"[^"]*){re.escape(old_name)}',
                        rf'\g<1>{new_name}',
                        text,
                    )

                # .Build.cs and .Target.cs: replace ALL occurrences
                # (class name, constructor, string references, etc.)
                if scope.rename_build_cs and file_path.suffix == ".cs":
                    text = text.replace(old_name, new_name)

                # Module macros: IMPLEMENT_MODULE, IMPLEMENT_GAME_MODULE
                if scope.rename_module_macros:
                    text = re.sub(
                        rf'(IMPLEMENT_\w*MODULE\s*\([^)]*){re.escape(old_name)}',
                        rf'\g<1>{new_name}',
                        text,
                    )
                    # F-prefixed class names: FOldNameModule → FNewNameModule
                    text = re.sub(
                        rf'\bF{re.escape(old_name)}(\w*Module)\b',
                        rf'F{new_name}\1',
                        text,
                    )

                # General identifier replacement in code (class names, log categories, etc.)
                # Be careful: only replace whole-word matches of the exact plugin name
                if scope.rename_modules:
                    # Module log category: DEFINE_LOG_CATEGORY(LogOldName)
                    text = re.sub(
                        rf'(Log){re.escape(old_name)}\b',
                        rf'\g<1>{new_name}',
                        text,
                    )

                # Comments
                if scope.rename_comments:
                    def _replace_in_comments(m):
                        return m.group(0).replace(old_name, new_name)
                    text = re.sub(rf'//[^\n]*\b{re.escape(old_name)}\b[^\n]*', _replace_in_comments, text)
                    text = re.sub(rf'/\*[\s\S]*?\*/', lambda m: m.group(0).replace(old_name, new_name) if old_name in m.group(0) else m.group(0), text)

                if text != original:
                    _write_text(file_path, text)
                    count += 1
                    self._log(f"  Updated: {file_path.relative_to(root)}", LogLevel.INFO)

            except Exception as e:
                errors.append(f"Failed to process {file_path}: {e}")

        return count, errors

    def _execute_file_renames(
        self,
        root: Path,
        old_name: str,
        new_name: str,
        scope: RenameScope,
    ) -> tuple:
        """Rename files containing old_name. Returns (count, errors)."""
        count = 0
        errors = []

        # Collect all files to rename (skip Intermediate/Binaries/etc.)
        files_to_rename = []
        for file_path in _walk_files(root):
            if old_name in file_path.name:
                files_to_rename.append(file_path)

        # Sort by depth (deepest first)
        files_to_rename.sort(key=lambda p: len(p.parts), reverse=True)

        for file_path in files_to_rename:
            new_file_name = file_path.name.replace(old_name, new_name)
            new_file_path = file_path.parent / new_file_name
            try:
                _safe_rename(file_path, new_file_path)
                count += 1
                self._log(f"  Renamed: {file_path.name} -> {new_file_name}", LogLevel.INFO)
            except Exception as e:
                errors.append(f"Failed to rename {file_path}: {e}")

        return count, errors

    def _execute_folder_renames(
        self,
        root: Path,
        old_name: str,
        new_name: str,
    ) -> tuple:
        """Rename folders containing old_name. Returns (count, errors)."""
        count = 0
        errors = []

        # Collect dirs (skip Intermediate/Binaries/etc.), sort deepest first
        folders_to_rename = []
        for dir_path in _walk_dirs(root):
            if old_name in dir_path.name and dir_path != root:
                folders_to_rename.append(dir_path)

        folders_to_rename.sort(key=lambda p: len(p.parts), reverse=True)

        for dir_path in folders_to_rename:
            new_dir_name = dir_path.name.replace(old_name, new_name)
            new_dir_path = dir_path.parent / new_dir_name
            try:
                _safe_rename(dir_path, new_dir_path)
                count += 1
                self._log(f"  Renamed dir: {dir_path.name} -> {new_dir_name}", LogLevel.INFO)
            except Exception as e:
                errors.append(f"Failed to rename dir {dir_path}: {e}")

        return count, errors


# ---------------------------------------------------------------------------
# ProjectRenamer
# ---------------------------------------------------------------------------

class ProjectRenamer:
    """
    Renames an Unreal Engine project: folders, files, source code,
    .uproject contents, .Target.cs files, and config entries.

    Usage:
        renamer = ProjectRenamer(log_callback=print_log)
        changes = renamer.preview(uproject_path, "OldProj", "NewProj", scope)
        result  = renamer.execute(uproject_path, "OldProj", "NewProj", scope)
    """

    def __init__(self, log_callback: Optional[LogCallback] = None, progress_callback: Optional[ProgressCallback] = None):
        self._log_callback = log_callback
        self._progress_callback = progress_callback

    def set_log_callback(self, callback: LogCallback) -> None:
        self._log_callback = callback

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        self._progress_callback = callback

    def _log(self, text: str, level: LogLevel = LogLevel.INFO) -> None:
        if self._log_callback:
            self._log_callback(LogMessage(text=text, level=level))

    def _progress(self, value: int) -> None:
        if self._progress_callback:
            self._progress_callback(min(100, max(0, value)))

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview(
        self,
        uproject_path: Path,
        old_name: str,
        new_name: str,
        scope: Optional[RenameScope] = None,
    ) -> List[RenameChange]:
        """Generate a preview of all changes for a project rename."""
        if scope is None:
            scope = RenameScope()

        uproject_path = Path(uproject_path).resolve()
        if not uproject_path.exists() or uproject_path.suffix != ".uproject":
            return []

        project_dir = uproject_path.parent
        changes: List[RenameChange] = []
        modules = self._parse_modules(uproject_path)
        self._progress(5)

        # 1) File system renames
        fs_previewer = PluginRenamer()
        changes.extend(fs_previewer._preview_filesystem(project_dir, old_name, new_name))
        self._progress(10)

        # 2) .uproject contents
        changes.extend(self._preview_uproject_contents(uproject_path, old_name, new_name, modules))

        # 3) .Target.cs content
        changes.extend(self._preview_target_files(project_dir, old_name, new_name))
        self._progress(15)

        # 4) Module content changes
        if scope.rename_modules:
            source_dir = project_dir / "Source"
            if source_dir.exists():
                n = max(len(modules), 1)
                for i, mod in enumerate(modules):
                    changes.extend(self._preview_module(project_dir, mod, old_name, new_name, scope))
                    self._progress(15 + int(10 * (i + 1) / n))

        # 5) Config files
        changes.extend(self._preview_config_files(project_dir, old_name, new_name))
        self._progress(30)

        # 6) Source code scan — bulk of work, gets per-file progress
        source_dir = project_dir / "Source"
        if source_dir.exists():
            scanner = PluginRenamer(progress_callback=self._progress_callback)
            changes.extend(scanner._preview_source_scan(
                source_dir, old_name, new_name, scope, progress_range=(30, 95),
            ))

        self._progress(100)
        return changes

    def _parse_modules(self, uproject_path: Path) -> List[Dict]:
        """Parse module list from .uproject."""
        try:
            text = _read_text(uproject_path)
            if not text:
                return []
            data = json.loads(text)
            return data.get("Modules", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _preview_uproject_contents(
        self, uproject_path: Path, old_name: str, new_name: str, modules: List[Dict]
    ) -> List[RenameChange]:
        changes = []
        for mod in modules:
            mod_name = mod.get("Name", "")
            if old_name in mod_name:
                changes.append(RenameChange(
                    change_type=ChangeType.CONTENT_REPLACE,
                    category=".uproject Contents",
                    file_path=uproject_path.name,
                    old_value=f'"Name": "{mod_name}"',
                    new_value=f'"Name": "{mod_name.replace(old_name, new_name)}"',
                ))
        return changes

    def _preview_target_files(
        self, project_dir: Path, old_name: str, new_name: str
    ) -> List[RenameChange]:
        changes = []
        source_dir = project_dir / "Source"
        if not source_dir.exists():
            return changes

        for target_file in source_dir.glob(f"{old_name}*.Target.cs"):
            new_target_name = target_file.name.replace(old_name, new_name)
            text = _read_text(target_file) or ""
            if old_name not in text:
                continue
            # Class name: class OldNameTarget : TargetRules
            pattern = rf'class\s+{re.escape(old_name)}\w*Target\s*:'
            for m in re.finditer(pattern, text):
                changes.append(RenameChange(
                    change_type=ChangeType.CONTENT_REPLACE,
                    category="Target Files",
                    file_path=f"Source/{new_target_name}",
                    old_value=m.group(0),
                    new_value=m.group(0).replace(old_name, new_name),
                ))
            # Constructor and other references (execute does full text.replace)
            occurrences = text.count(old_name)
            class_matches = len(re.findall(pattern, text))
            extra = occurrences - class_matches
            if extra > 0:
                changes.append(RenameChange(
                    change_type=ChangeType.CONTENT_REPLACE,
                    category="Target Files",
                    file_path=f"Source/{new_target_name}",
                    old_value=f"{old_name} ({extra} additional references)",
                    new_value=new_name,
                ))

        return changes

    def _preview_module(
        self, project_dir: Path, module: Dict, old_name: str, new_name: str, scope: RenameScope
    ) -> List[RenameChange]:
        """Reuse PluginRenamer module preview logic."""
        changes = []
        mod_name = module.get("Name", "")
        mod_type = module.get("Type", "Runtime")
        new_mod_name = mod_name.replace(old_name, new_name) if old_name in mod_name else mod_name
        category = f"Module: {mod_name} ({mod_type})"

        source_dir = project_dir / "Source"
        mod_folder = source_dir / mod_name

        # Build.cs content change (file/folder renames are in File System)
        if mod_folder.exists() and scope.rename_build_cs:
            build_cs = mod_folder / f"{mod_name}.Build.cs"
            if build_cs.exists() and old_name in mod_name:
                text = _read_text(build_cs) or ""
                if f"class {mod_name}" in text:
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category=category,
                        file_path=f"{new_mod_name}.Build.cs",
                        old_value=f"class {mod_name} : ModuleRules",
                        new_value=f"class {new_mod_name} : ModuleRules",
                    ))
                ctor_pattern = rf'public\s+{re.escape(mod_name)}\s*\('
                if re.search(ctor_pattern, text):
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category=category,
                        file_path=f"{new_mod_name}.Build.cs",
                        old_value=f"public {mod_name}(ReadOnlyTargetRules Target)",
                        new_value=f"public {new_mod_name}(ReadOnlyTargetRules Target)",
                    ))

        # IMPLEMENT_MODULE / IMPLEMENT_GAME_MODULE
        if mod_folder.exists() and scope.rename_module_macros:
            for cpp_file in _walk_files(mod_folder, {".cpp"}):
                text = _read_text(cpp_file) or ""
                pattern = rf'IMPLEMENT_\w*MODULE\s*\([^)]*{re.escape(old_name)}[^)]*\)'
                for match in re.finditer(pattern, text):
                    changes.append(RenameChange(
                        change_type=ChangeType.CONTENT_REPLACE,
                        category=category,
                        file_path=str(cpp_file.relative_to(project_dir)),
                        old_value=match.group(0),
                        new_value=match.group(0).replace(old_name, new_name),
                    ))

        return changes

    def _preview_config_files(
        self, project_dir: Path, old_name: str, new_name: str
    ) -> List[RenameChange]:
        changes = []
        config_dir = project_dir / "Config"
        if not config_dir.exists():
            return changes

        for ini_file in config_dir.rglob("*.ini"):
            text = _read_text(ini_file) or ""
            if old_name in text:
                rel = str(ini_file.relative_to(project_dir))
                occurrences = text.count(old_name)
                changes.append(RenameChange(
                    change_type=ChangeType.CONTENT_REPLACE,
                    category="Config Files",
                    file_path=rel,
                    old_value=f"{old_name} ({occurrences} occurrences)",
                    new_value=new_name,
                ))
        return changes

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(
        self,
        uproject_path: Path,
        old_name: str,
        new_name: str,
        scope: Optional[RenameScope] = None,
    ) -> RenameResult:
        """Execute a full project rename."""
        if scope is None:
            scope = RenameScope()

        start_time = time.time()
        uproject_path = Path(uproject_path).resolve()
        project_dir = uproject_path.parent
        errors: List[str] = []
        changes_applied = 0
        backup_path = None

        # Validation
        if not uproject_path.exists():
            return RenameResult(RenameStatus.FAILED, f"File not found: {uproject_path}")
        if not re.match(r'^[A-Za-z][A-Za-z0-9]*$', new_name):
            return RenameResult(RenameStatus.FAILED, f"Invalid name: {new_name}")
        if old_name == new_name:
            return RenameResult(RenameStatus.FAILED, "Old and new names are identical")

        # Backup
        if scope.create_backup:
            backup_path = project_dir.parent / f"{project_dir.name}_backup_{int(time.time())}"
            self._log(f"Creating backup: {backup_path}", LogLevel.INFO)
            try:
                shutil.copytree(project_dir, backup_path, ignore=shutil.ignore_patterns(
                    "Binaries", "Intermediate", "DerivedDataCache", "Saved", ".vs", ".idea",
                ))
            except (OSError, shutil.Error) as e:
                return RenameResult(RenameStatus.FAILED, f"Backup failed: {e}")

        try:
            # Phase 1: .uproject content
            self._log("Phase 1: Updating .uproject contents...", LogLevel.INFO)
            count, errs = self._execute_uproject_update(project_dir, old_name, new_name)
            changes_applied += count
            errors.extend(errs)

            # Phase 2: Config files
            self._log("Phase 2: Updating config files...", LogLevel.INFO)
            count, errs = self._execute_config_update(project_dir, old_name, new_name)
            changes_applied += count
            errors.extend(errs)

            # Phase 3: Source content replacements (same as plugin)
            self._log("Phase 3: Updating source files...", LogLevel.INFO)
            pr = PluginRenamer(log_callback=self._log_callback)
            count, errs = pr._execute_content_replacements(project_dir, old_name, new_name, scope)
            changes_applied += count
            errors.extend(errs)

            # Phase 4: .Target.cs content
            self._log("Phase 4: Updating Target files...", LogLevel.INFO)
            count, errs = self._execute_target_update(project_dir, old_name, new_name)
            changes_applied += count
            errors.extend(errs)

            # Phase 5: Rename files
            self._log("Phase 5: Renaming files...", LogLevel.INFO)
            count, errs = pr._execute_file_renames(project_dir, old_name, new_name, scope)
            changes_applied += count
            errors.extend(errs)

            # Phase 6: Rename folders
            self._log("Phase 6: Renaming folders...", LogLevel.INFO)
            count, errs = pr._execute_folder_renames(project_dir, old_name, new_name)
            changes_applied += count
            errors.extend(errs)

            # Phase 7: Rename project root
            if project_dir.name == old_name:
                new_dir = project_dir.parent / new_name
                self._log(f"Renaming project root: {project_dir.name} -> {new_name}", LogLevel.INFO)
                try:
                    _safe_rename(project_dir, new_dir)
                    changes_applied += 1
                except (OSError, FileExistsError) as e:
                    errors.append(f"Failed to rename root: {e}")

        except Exception as e:
            self._log(f"Rename failed: {e}", LogLevel.ERROR)
            return RenameResult(
                status=RenameStatus.FAILED,
                message=str(e),
                changes_applied=changes_applied,
                duration_seconds=time.time() - start_time,
                errors=errors,
                backup_path=backup_path,
            )

        duration = time.time() - start_time
        if errors:
            self._log(f"Completed with {len(errors)} errors", LogLevel.WARNING)
        else:
            self._log(f"Rename complete: {changes_applied} changes in {duration:.1f}s", LogLevel.SUCCESS)

        return RenameResult(
            status=RenameStatus.SUCCESS if not errors else RenameStatus.FAILED,
            message=f"Applied {changes_applied} changes" + (f" ({len(errors)} errors)" if errors else ""),
            changes_applied=changes_applied,
            duration_seconds=duration,
            errors=errors,
            backup_path=backup_path,
        )

    def _execute_uproject_update(self, project_dir: Path, old_name: str, new_name: str) -> tuple:
        count = 0
        errors = []
        for uproject in project_dir.glob("*.uproject"):
            try:
                text = _read_text(uproject)
                if text and old_name in text:
                    data = json.loads(text)
                    changed = False
                    for mod in data.get("Modules", []):
                        if old_name in mod.get("Name", ""):
                            mod["Name"] = mod["Name"].replace(old_name, new_name)
                            changed = True
                    if changed:
                        _write_text(uproject, json.dumps(data, indent="\t", ensure_ascii=False))
                        count += 1
            except Exception as e:
                errors.append(f"Failed to update {uproject}: {e}")
        return count, errors

    def _execute_config_update(self, project_dir: Path, old_name: str, new_name: str) -> tuple:
        count = 0
        errors = []
        config_dir = project_dir / "Config"
        if not config_dir.exists():
            return count, errors

        for ini_file in config_dir.rglob("*.ini"):
            try:
                text = _read_text(ini_file)
                if text and old_name in text:
                    new_text = text.replace(old_name, new_name)
                    if new_text != text:
                        _write_text(ini_file, new_text)
                        count += 1
                        self._log(f"  Updated: {ini_file.relative_to(project_dir)}", LogLevel.INFO)
            except Exception as e:
                errors.append(f"Failed to update {ini_file}: {e}")
        return count, errors

    def _execute_target_update(self, project_dir: Path, old_name: str, new_name: str) -> tuple:
        count = 0
        errors = []
        source_dir = project_dir / "Source"
        if not source_dir.exists():
            return count, errors

        for target_file in source_dir.glob("*.Target.cs"):
            try:
                text = _read_text(target_file)
                if text and old_name in text:
                    new_text = text.replace(old_name, new_name)
                    if new_text != text:
                        _write_text(target_file, new_text)
                        count += 1
                        self._log(f"  Updated: {target_file.name}", LogLevel.INFO)
            except Exception as e:
                errors.append(f"Failed to update {target_file}: {e}")
        return count, errors
