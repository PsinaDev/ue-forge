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

from framekit.types import LogLevel, LogMessage


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
    """A discovered commandlet parameter or switch.

    Extra fields (backward compatible with page.py which reads only
    name/description/has_value/default_value):
        value_hint:  placeholder for the value form, e.g. "platform", "filename".
        aliases:     alternate spellings found in source (same meaning, different case/name).
        source_kind: first source that produced this param ("fparse_value",
                     "fparse_param", "switches", "paramvals", "help_block",
                     "usage_text", "print_help"). Diagnostic only.
        is_negated:  true when at least one occurrence was '!FParse::Param(...)'
                     (inverting flag). Not rendered by UI; reserved for future.
    """
    name: str
    description: str = ""
    has_value: bool = False
    default_value: str = ""
    value_hint: str = ""
    aliases: list[str] = field(default_factory=list)
    source_kind: str = ""
    is_negated: bool = False


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
                hint = p.value_hint.strip() or "value"
                parts.append(f"-{p.name}=<{hint}>")
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

# Parameter patterns found in commandlet source.
# Each entry: (regex, source_kind, has_value_by_default).
# Order matters: more specific patterns (negated, '=' form) come before generic.
_PARAM_PATTERNS: list[tuple[re.Pattern[str], str, bool]] = [
    # !FParse::Param(..., TEXT("Name"))   - inverting flag
    (re.compile(
        r'!\s*FParse::Param\s*\([^,]+,\s*TEXT\(\s*"-?(\w+)"\s*\)',
    ), "fparse_param_negated", False),
    # FParse::Value(..., TEXT("Name=") or TEXT("Name"))
    (re.compile(
        r'\bFParse::Value\s*\([^,]+,\s*TEXT\(\s*"-?(\w+)=?"\s*\)',
    ), "fparse_value", True),
    # FParse::Bool(..., TEXT("Name"), ...)
    (re.compile(
        r'\bFParse::Bool\s*\([^,]+,\s*TEXT\(\s*"-?(\w+)"\s*\)',
    ), "fparse_bool", True),
    # FParse::Param(..., TEXT("Name"))
    (re.compile(
        r'\bFParse::Param\s*\([^,]+,\s*TEXT\(\s*"-?(\w+)"\s*\)',
    ), "fparse_param", False),
    # Switches.Contains("Name") or Switches.Contains(TEXT("Name"))
    (re.compile(
        r'\bSwitches\s*\.\s*Contains\s*\(\s*(?:TEXT\s*\(\s*)?"-?(\w+)"\s*\)?\s*\)',
    ), "switches", False),
    # ParamVals.Find(TEXT("Name")) / .FindRef / .Contains / ParamVals[TEXT("Name")]
    # Optional FString(...) wrapper: ParamVals.Find(FString(TEXT("Config")))
    (re.compile(
        r'\bParamVals\s*(?:\.\s*(?:Find|FindRef|Contains)\s*\(|\[)\s*'
        r'(?:FString\s*\(\s*)?TEXT\(\s*"-?(\w+)"\s*\)',
    ), "paramvals", True),
]

# Names to ignore when harvested from source — these are not user-facing params.
_NOISE_NAMES: frozenset[str] = frozenset({
    "run", "game", "log", "editor", "server", "client",
    "commandlet", "cmdlet", "help",
})

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

# Bare TEXT("...") — used inside concatenated UsageText string literals where
# there is no surrounding UE_LOG wrapper. Applied only to pre-extracted blocks.
_BARE_TEXT_RE = re.compile(r'TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)')

# Help-line formats (tried in order, first match wins per line):

# 1. "-name=<placeholder>   Description text"
_HELP_LINE_ANGLE_RE = re.compile(
    r"^\s*-(\w+)=<([^>]+)>\s{2,}(.+?)\s*$",
)
# 2. "-name=VALUE   Description text"  (VALUE is literal placeholder like "filename")
_HELP_LINE_EQ_RE = re.compile(
    r"^\s*-(\w+)=(\S+)\s{2,}(.+?)\s*$",
)
# 3. "-name   Description text"
_HELP_LINE_FLAG_RE = re.compile(
    r"^\s*-(\w+)\s{2,}(.+?)\s*$",
)
# 4. "Required: -name=<placeholder>   (Description text)"
_HELP_LINE_LABELED_RE = re.compile(
    r"^\s*(?:Required|Optional)\s*:\s*-(\w+)"
    r"(?:=<([^>]+)>|=(\S+))?"
    r"\s*\((.+?)\)?\s*$",
    re.IGNORECASE,
)
# 5. UsageText tab-separated form: "Preview\t Runs the commandlet..."
#    (NO leading dash, used only for usage_text blocks.)
_HELP_LINE_TAB_RE = re.compile(
    r"^\s*(\w+)\s*\\t+\s*(.+?)\s*$",
)

# Header lines to skip (not descriptions, not params)
_HELP_HEADER_WORDS: frozenset[str] = frozenset({
    "options", "parameters", "usage", "switches", "arguments", "flags",
})

# Usage-example heuristics inside help blocks
_USAGE_HINT_SUBSTRINGS: tuple[str, ...] = (
    "-run=", "editor-cmd", "unrealeditor-cmd", "ue4editor-cmd",
)

# Placeholders that mark a line as a usage-example rather than a param definition
_USAGE_PLACEHOLDER_RE = re.compile(
    r"<\s*(?:GameName|YourProject|YourGame|project|ProjectName|UProject)\s*>",
    re.IGNORECASE,
)

# Harvest inline parameters from a usage-example line: "-name=<hint>" or "-name=VALUE"
_INLINE_PARAM_RE = re.compile(
    r"-(\w+)(?:=<([^>]+)>|=(\S+))?",
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


def _extract_params_from_text(text: str) -> list[CommandletParam]:
    """Scan raw C++ source text for parameter usage patterns.

    Same logic as :func:`_extract_params_from_cpp`, but takes a string so it
    can be invoked on a class-scoped slice of a multi-class .cpp.
    """
    found: dict[str, CommandletParam] = {}
    for pattern, kind, has_value in _PARAM_PATTERNS:
        is_negated_pattern = kind.endswith("_negated")
        base_kind = kind.replace("_negated", "")
        for match in pattern.finditer(text):
            raw = match.group(1).lstrip("-")
            if len(raw) <= 1:
                continue
            if raw.casefold() in _NOISE_NAMES:
                continue
            key = raw.casefold()
            existing = found.get(key)
            if existing is None:
                found[key] = CommandletParam(
                    name=raw,
                    has_value=has_value,
                    source_kind=base_kind,
                    is_negated=is_negated_pattern,
                )
            else:
                existing.has_value = existing.has_value or has_value
                existing.is_negated = existing.is_negated or is_negated_pattern
                if raw != existing.name and raw not in existing.aliases:
                    existing.aliases.append(raw)
    return list(found.values())


def _extract_params_from_cpp(cpp_path: Path) -> list[CommandletParam]:
    """Scan a .cpp file for parameter usage patterns.

    Deduplicates case-insensitively (UE command-line is case-insensitive),
    collects alternate spellings into ``aliases``, and flips ``is_negated``
    when '!FParse::Param(...)' occurrences are seen.
    """
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return _extract_params_from_text(text)


def _extract_help_text_from_text(text: str) -> str:
    """Scan C++ source text for HelpDescription / HelpUsage field assignments."""
    m = re.search(
        r'HelpDescription\s*=\s*TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)',
        text,
    )
    if m:
        return m.group(1).replace("\\n", "\n").replace('\\"', '"')

    m = re.search(
        r'HelpUsage\s*=\s*TEXT\(\s*"((?:[^"\\]|\\.)*)"\s*\)',
        text,
    )
    if m:
        return m.group(1).replace("\\n", "\n").replace('\\"', '"')

    return ""


def _extract_help_text(cpp_path: Path) -> str:
    """Try to extract HelpDescription or help text from constructor."""
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return _extract_help_text_from_text(text)


def _extract_balanced_braces(text: str, start_pos: int) -> Optional[str]:
    """Extract content between matching braces starting from ``start_pos``.

    ``start_pos`` must point at or past the opening '{'. Returns the contents
    without the outer braces, or None when the braces are unbalanced.
    """
    brace_pos = text.find("{", start_pos)
    if brace_pos == -1 or brace_pos > start_pos + 60:
        return None
    depth = 1
    pos = brace_pos + 1
    while pos < len(text) and depth > 0:
        ch = text[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        pos += 1
    if depth != 0:
        return None
    return text[brace_pos + 1:pos - 1]


def _find_help_block(text: str) -> Optional[str]:
    """
    Find the help block in Main() that handles -help switch.

    Looks for patterns like:
        if (Switches.Contains("help"))
        if (Switches.Contains(TEXT("help")))
        if (FParse::Param(..., TEXT("help")))
    """
    help_patterns = [
        r'Switches\s*\.\s*Contains\s*\(\s*(?:TEXT\s*\()?\s*"help"',
        r'FParse::Param\s*\([^,]+,\s*TEXT\(\s*"help"\s*\)',
        r'Contains\s*\(\s*TEXT\(\s*"-?help"\s*\)',
    ]
    for pattern in help_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        block = _extract_balanced_braces(text, match.end())
        if block is not None:
            return block
    return None


# Declarations of help-printing lambdas/functions (captures identifier name)
_PRINT_HELP_DECL_RE = re.compile(
    r"\b(?:auto|static|void|int|int32)\s+(?:\w+::)?"
    r"(\w*[Hh]elp\w*)\s*"
    r"(?:=\s*\[[^\]]*\][^{]*)?"
    r"\(\s*\)\s*(?:->\s*\w+\s*)?\{",
    re.MULTILINE,
)

# const FString [Class::]UsageText(...) — concatenated TEXT(...) literals
_USAGE_TEXT_DECL_RE = re.compile(
    r"\bconst\s+FString\s+(?:\w+::)?\w*(?:UsageText|HelpText|UsageString)\w*"
    r"\s*\(([\s\S]*?)\)\s*;",
    re.MULTILINE,
)


def _find_print_help_bodies(text: str) -> list[str]:
    """Extract bodies of help-printing lambdas/functions (PrintHelp, ShowHelp, ...).

    Catches patterns like::

        auto PrintHelp = []() { UE_LOG(...); ... };
        void UFoo::PrintHelp() { UE_LOG(...); ... }
        static void ShowHelp() { ... }
    """
    bodies: list[str] = []
    seen: set[int] = set()
    for match in _PRINT_HELP_DECL_RE.finditer(text):
        ident = match.group(1)
        if ident.casefold() in {"helper", "helpers", "helped"}:
            continue
        body = _extract_balanced_braces(text, match.end() - 1)
        if body is None or match.start() in seen:
            continue
        seen.add(match.start())
        bodies.append(body)
    return bodies


def _find_usage_text_strings(text: str) -> list[str]:
    """Extract content of const-FString usage/help string declarations.

    The content is a sequence of concatenated ``TEXT("...")`` literals;
    they are joined with newlines so that the result can be fed to the
    same line-based parser used for regular help blocks.
    """
    results: list[str] = []
    for match in _USAGE_TEXT_DECL_RE.finditer(text):
        raw = match.group(1)
        pieces = [m.group(1) for m in _BARE_TEXT_RE.finditer(raw)]
        if not pieces:
            continue
        joined = "\n".join(pieces)
        results.append(joined)
    return results


def _try_parse_help_line(
    line: str,
    *,
    allow_tab_form: bool,
) -> Optional[CommandletParam]:
    """Try each known help-line format. Returns parsed param or None.

    ``allow_tab_form`` enables the UsageText-specific pattern
    ``"Name\\t Description"`` (no leading dash). Enabled only when parsing
    blocks extracted from ``const FString UsageText(...)`` declarations.
    """
    labeled = _HELP_LINE_LABELED_RE.match(line)
    if labeled:
        name = labeled.group(1)
        angle_hint = labeled.group(2) or ""
        eq_value = labeled.group(3) or ""
        desc = labeled.group(4).strip().rstrip(")").strip()
        return CommandletParam(
            name=name,
            description=desc,
            has_value=bool(angle_hint or eq_value),
            value_hint=angle_hint,
            source_kind="help_block",
        )

    angle = _HELP_LINE_ANGLE_RE.match(line)
    if angle:
        return CommandletParam(
            name=angle.group(1),
            description=angle.group(3).strip(),
            has_value=True,
            value_hint=angle.group(2).strip(),
            source_kind="help_block",
        )

    eq = _HELP_LINE_EQ_RE.match(line)
    if eq:
        return CommandletParam(
            name=eq.group(1),
            description=eq.group(3).strip(),
            has_value=True,
            value_hint=eq.group(2).strip(),
            source_kind="help_block",
        )

    flag = _HELP_LINE_FLAG_RE.match(line)
    if flag:
        return CommandletParam(
            name=flag.group(1),
            description=flag.group(2).strip(),
            has_value=False,
            source_kind="help_block",
        )

    if allow_tab_form:
        tab = _HELP_LINE_TAB_RE.match(line)
        if tab:
            return CommandletParam(
                name=tab.group(1),
                description=tab.group(2).strip(),
                has_value=False,
                source_kind="usage_text",
            )

    return None


def _looks_like_usage_example(line: str) -> bool:
    """Heuristic: does this line look like a full command-line example?"""
    low = line.lower()
    if any(hint in low for hint in _USAGE_HINT_SUBSTRINGS):
        return True
    # Lines that open with a project placeholder like "<GameName> CommandletName ..."
    # are usage examples too, even without -run= (common in UsageText strings).
    if _USAGE_PLACEHOLDER_RE.search(line):
        return True
    return False


def _harvest_inline_params(line: str) -> list[CommandletParam]:
    """Extract -name[=<hint>|=VALUE] occurrences from a usage-example line.

    Used for lines recognised as usage examples: they contain real parameter
    names which would otherwise be lost (no dedicated param-description line).
    Returned params have empty description — they only confirm existence and
    may carry a value_hint extracted from the ``<placeholder>`` form.
    """
    results: list[CommandletParam] = []
    for match in _INLINE_PARAM_RE.finditer(line):
        name = match.group(1)
        angle_hint = match.group(2) or ""
        eq_value = match.group(3) or ""
        if name.casefold() in _NOISE_NAMES:
            continue
        if len(name) <= 1:
            continue
        results.append(CommandletParam(
            name=name,
            description="",
            has_value=bool(angle_hint or eq_value),
            value_hint=angle_hint,
            source_kind="usage_text",
        ))
    return results


def _parse_help_block(
    help_block: str,
    *,
    source: str,
) -> tuple[str, list[CommandletParam], list[str]]:
    """Parse lines harvested from a help block.

    ``source`` is one of ``"if_block"``, ``"print_help"``, ``"usage_text"``.
    ``"usage_text"`` enables the tab-separated line form which is too loose
    to apply outside explicit UsageText blocks.

    Returns:
        (description, params, examples) — examples are usage-example lines
        extracted from inside the block (full command-line invocations).
    """
    description_lines: list[str] = []
    params: dict[str, CommandletParam] = {}
    examples: list[str] = []

    if source == "usage_text":
        # UsageText content is already a sequence of raw TEXT("...") pieces
        # joined by '\n'; treat every non-empty line as a candidate.
        raw_lines = help_block.splitlines()
    else:
        # Inside an if-block or lambda, extract only what appears inside
        # UE_LOG(..., TEXT("..."))
        raw_lines = [m.group(1) for m in _UE_LOG_TEXT_RE.finditer(help_block)]

    allow_tab = (source == "usage_text")

    for raw in raw_lines:
        # Normalize literal escapes coming from C++ string literals.
        normalized = raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace('\\"', '"')
        for piece in normalized.splitlines():
            line = piece.strip()
            if not line:
                continue

            if _looks_like_usage_example(line):
                examples.append(line)
                for inline in _harvest_inline_params(line):
                    key = inline.name.casefold()
                    existing = params.get(key)
                    if existing is None:
                        params[key] = inline
                    else:
                        if not existing.value_hint and inline.value_hint:
                            existing.value_hint = inline.value_hint
                        existing.has_value = existing.has_value or inline.has_value
                        if inline.name != existing.name and inline.name not in existing.aliases:
                            existing.aliases.append(inline.name)
                continue

            if line.lower().rstrip(":").strip() in _HELP_HEADER_WORDS:
                continue

            param = _try_parse_help_line(line, allow_tab_form=allow_tab)
            if param is not None:
                if param.name.casefold() in _NOISE_NAMES:
                    # Recognised as a param but name is noise (e.g. "-help");
                    # drop entirely — do NOT leak into description.
                    continue
                key = param.name.casefold()
                existing = params.get(key)
                if existing is None:
                    params[key] = param
                else:
                    if not existing.description and param.description:
                        existing.description = param.description
                    if not existing.value_hint and param.value_hint:
                        existing.value_hint = param.value_hint
                    existing.has_value = existing.has_value or param.has_value
                    if param.name != existing.name and param.name not in existing.aliases:
                        existing.aliases.append(param.name)
                continue

            description_lines.append(line)

    description = "\n".join(description_lines).strip()
    return description, list(params.values()), examples


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


def _extract_help_block_data_from_text(
    text: str,
) -> tuple[str, list[CommandletParam], list[str]]:
    """Text-driven variant of :func:`_extract_help_block_data`.

    Does not read any file and does not invoke comment-scraping fallbacks
    (those are path-based and belong to the .cpp-level helper).
    """
    descriptions: list[str] = []
    params: dict[str, CommandletParam] = {}
    examples: list[str] = []

    block_sources: list[tuple[str, str]] = []

    direct = _find_help_block(text)
    if direct:
        block_sources.append(("if_block", direct))

    for body in _find_print_help_bodies(text):
        block_sources.append(("print_help", body))

    for usage in _find_usage_text_strings(text):
        block_sources.append(("usage_text", usage))

    for kind, block in block_sources:
        desc, parsed, ex = _parse_help_block(block, source=kind)
        if desc:
            descriptions.append(desc)
        examples.extend(ex)
        for p in parsed:
            key = p.name.casefold()
            existing = params.get(key)
            if existing is None:
                params[key] = p
            else:
                if not existing.description and p.description:
                    existing.description = p.description
                if not existing.value_hint and p.value_hint:
                    existing.value_hint = p.value_hint
                existing.has_value = existing.has_value or p.has_value
                if p.name != existing.name and p.name not in existing.aliases:
                    existing.aliases.append(p.name)

    description = "\n".join(dict.fromkeys(descriptions)).strip()
    deduped_examples = list(dict.fromkeys(examples))
    return description, list(params.values()), deduped_examples


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

    description, params, examples = _extract_help_block_data_from_text(text)

    fallback_examples = _extract_usage_examples(cpp_path)
    for ex in fallback_examples:
        if ex not in examples:
            examples.append(ex)

    return description, params, examples


def _extract_cpp_description_from_text(text: str, class_name: str) -> str:
    """Text-driven variant of :func:`_extract_cpp_description`."""
    ctor_pattern = re.compile(
        re.escape(class_name) + r"::" + re.escape(class_name) + r"\s*\(",
    )
    m = ctor_pattern.search(text)
    if not m:
        return ""

    before = text[:m.start()]

    cm = re.search(r"/\*\*?([\s\S]*?)\*/\s*$", before)
    if cm:
        cleaned = _clean_comment(cm.group(0))
        if cleaned and len(cleaned) > 20:
            return cleaned

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
    return _extract_cpp_description_from_text(text, class_name)


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


    return None


# ---------------------------------------------------------------------------
# Cross-file implementation lookup
# ---------------------------------------------------------------------------

# Matches "UClassName::" appearing at a definition site
# (method def, static member def, free-function scope). Used both to build
# the file→classes index and to locate class-scoped regions inside a .cpp.
_CLASS_QUALIFIER_RE = re.compile(r"\b(U\w+Commandlet)::")


def _build_cpp_index(root: Path) -> dict[str, list[Path]]:
    """Index: class_name -> list of .cpp files that reference ``ClassName::``.

    One pass over every ``.cpp`` in ``root`` (respecting ``_SKIP_DIRS``). The
    same class can be referenced by several files (e.g. forward decls in
    foreign .cpp, or helpers); callers are expected to verify by scoping.
    """
    index: dict[str, list[Path]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".cpp"):
                continue
            cpp = Path(dirpath) / fn
            try:
                text = cpp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            seen_in_file: set[str] = set()
            for match in _CLASS_QUALIFIER_RE.finditer(text):
                cls = match.group(1)
                if cls in seen_in_file:
                    continue
                seen_in_file.add(cls)
                index.setdefault(cls, []).append(cpp)
    return index


def _extract_class_scope(text: str, class_name: str) -> str:
    """Return the concatenation of all regions in ``text`` that belong to
    ``UClassName`` — method bodies, ctor/dtor, and file-scope definitions
    (``const FString UClassName::UsageText(...);``).

    This avoids cross-contamination when several commandlet classes share a
    single .cpp. Returns empty string when the class has no definitions.
    """
    parts: list[str] = []
    escaped = re.escape(class_name)

    # 1. Method/ctor definitions: "[<return-ish>] UClassName::Name(args) [const] {"
    # The signature may span several lines; we accept anything except ';' and '{'
    # between the ')' and the opening '{' to handle ctor initializer lists
    # (": Base(...), Field(val)") as well as C++ trailing-return/cv qualifiers.
    # The leading "return type" part is optional — constructors have no return
    # type and are written "UFoo::UFoo(...) : ... {".
    method_re = re.compile(
        r"(?:^|\n)[\w:<>,&*\s\[\]]*?\b"
        + escaped
        + r"::\w+\s*\([^;{}]*?\)\s*(?:const\s*)?"
        r"(?::[^{;]+)?"
        r"\{",
    )
    for match in method_re.finditer(text):
        body = _extract_balanced_braces(text, match.end() - 1)
        if body is not None:
            parts.append(body)

    # 2. File-scope variable definitions with parenthesised initializer, e.g.
    # "const FString UClass::UsageText(TEXT("...") TEXT("..."));"
    var_re = re.compile(
        r"(?:^|\n)[\w:<>,&*\s\[\]]*?\b"
        + escaped
        + r"::\w+\s*\([\s\S]*?\)\s*;",
    )
    for match in var_re.finditer(text):
        parts.append(match.group(0))

    return "\n".join(parts)


def _merge_param_into(target: dict[str, CommandletParam], src: CommandletParam) -> None:
    """Additive merge of ``src`` into the ``target`` dict keyed by casefolded name.

    description / value_hint: first non-empty wins.
    has_value / is_negated:  OR across sources.
    aliases:                 union of alternate spellings.
    """
    key = src.name.casefold()
    existing = target.get(key)
    if existing is None:
        target[key] = src
        return
    if not existing.description and src.description:
        existing.description = src.description
    if not existing.value_hint and src.value_hint:
        existing.value_hint = src.value_hint
    existing.has_value = existing.has_value or src.has_value
    existing.is_negated = existing.is_negated or src.is_negated
    if src.name != existing.name and src.name not in existing.aliases:
        existing.aliases.append(src.name)
    for alias in src.aliases:
        if alias != existing.name and alias not in existing.aliases:
            existing.aliases.append(alias)


def _collect_from_cpp(
    cpp_path: Path,
    class_name: str,
) -> tuple[list[CommandletParam], str, list[str], str, str]:
    """Extract params / description / examples / help_text / cpp-comment-desc
    for a single commandlet class from a .cpp file.

    If ``class_name`` occurs in the file, only regions belonging to that class
    are scanned, so neighbouring classes in the same .cpp do not leak. If the
    class is not referenced at all (e.g. the file is the canonical per-class
    source), the whole file text is used — preserving prior behaviour for
    one-class-per-file layouts.
    """
    try:
        text = cpp_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], "", [], "", ""

    scope = _extract_class_scope(text, class_name)
    if not scope:
        scope = text

    basic = _extract_params_from_text(scope)
    help_desc, help_params, examples = _extract_help_block_data_from_text(scope)
    help_text = _extract_help_text_from_text(scope)
    cpp_desc = _extract_cpp_description_from_text(scope, class_name) or \
               _extract_cpp_description_from_text(text, class_name)

    merged: dict[str, CommandletParam] = {}
    for p in help_params:
        _merge_param_into(merged, p)
    for p in basic:
        _merge_param_into(merged, p)

    return list(merged.values()), help_desc, examples, help_text, cpp_desc


def scan_directory(
    root: Path,
    source: CommandletSource,
    progress_callback: Optional[ProgressCallback] = None,
) -> list[CommandletInfo]:
    """
    Recursively scan a directory for commandlet class declarations.

    Uses os.walk with directory pruning to avoid stack overflow
    on large UE projects (known issue with rglob).

    For each commandlet class discovered in a .h file, implementation is
    resolved in two stages:
      1. Per-header heuristic (``_find_matching_cpp``) — fast path for the
         common one-class-per-file layout.
      2. Cross-file index built from every .cpp — handles the case where
         several commandlets share one .cpp (e.g. ``ContentCommandlets.cpp``
         hosts ``UResavePackagesCommandlet`` and five others).

    Data harvested from implementations is merged additively; no source is
    considered authoritative.
    """
    commandlets: list[CommandletInfo] = []
    header_files: list[Path] = []

    # Phase 1: collect header files
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".h"):
                header_files.append(Path(dirpath) / fn)

    total = len(header_files)
    if total == 0:
        return commandlets

    # Phase 1b: cross-file index of UXxxCommandlet:: references.
    cpp_index = _build_cpp_index(root)

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

            # Resolve implementation file(s).
            candidate_cpps: list[Path] = []
            primary = _find_matching_cpp(header)
            if primary is not None:
                candidate_cpps.append(primary)
            for cpp in cpp_index.get(class_name, []):
                if cpp not in candidate_cpps:
                    candidate_cpps.append(cpp)

            merged_params: dict[str, CommandletParam] = {}
            help_desc_parts: list[str] = []
            examples: list[str] = []
            help_text = ""
            cpp_desc = ""

            for cpp in candidate_cpps:
                cpp_params, cpp_help_desc, cpp_examples, cpp_help_text, cpp_cdesc = \
                    _collect_from_cpp(cpp, class_name)
                for p in cpp_params:
                    _merge_param_into(merged_params, p)
                if cpp_help_desc:
                    help_desc_parts.append(cpp_help_desc)
                for ex in cpp_examples:
                    if ex not in examples:
                        examples.append(ex)
                if not help_text and cpp_help_text:
                    help_text = cpp_help_text
                if not cpp_desc and cpp_cdesc:
                    cpp_desc = cpp_cdesc

            # Legacy comment-scraped examples from the primary .cpp (// Examples:)
            if primary is not None:
                for ex in _extract_usage_examples(primary):
                    if ex not in examples:
                        examples.append(ex)

            params = list(merged_params.values())

            # description precedence: header doc-comment wins, then UE_LOG help,
            # then ctor-leading comment in .cpp.
            if not description and help_desc_parts:
                description = "\n".join(dict.fromkeys(help_desc_parts)).strip()
            if not description and cpp_desc:
                description = cpp_desc

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
    from ue_forge.config import get_ue_config_manager as get_config_manager
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
    from ue_forge.platform import ue_platform_handler as platform_handler
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