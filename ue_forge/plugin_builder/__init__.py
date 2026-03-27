"""
UE Forge — Plugin Builder module.

Build Unreal Engine plugins from source with automated UAT integration.
Can run standalone or as a page in the UE Forge host window.
"""

from . import strings  # noqa: F401 — register translations

from .types import (
    BuildStatus,
    LogLevel,
    LogMessage,
    PluginInfo,
    ModuleInfo,
    PluginDependency,
    EngineInfo,
    BuildConfig,
    BuildResult,
)
from .engine_finder import EngineFinder
from .builder import PluginBuilder, parse_extra_params
from .page import PluginBuilderPage

__all__ = [
    "BuildStatus",
    "LogLevel",
    "LogMessage",
    "PluginInfo",
    "ModuleInfo",
    "PluginDependency",
    "EngineInfo",
    "BuildConfig",
    "BuildResult",
    "EngineFinder",
    "PluginBuilder",
    "parse_extra_params",
    "PluginBuilderPage",
]
