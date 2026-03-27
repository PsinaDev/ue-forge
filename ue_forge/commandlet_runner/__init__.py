"""
Commandlet Runner module for UE Forge.

Discovers and executes Unreal Engine commandlets with parameter
generation and live console output.
"""

from . import strings  # noqa: F401 — register translations

from .page import CommandletRunnerPage

__all__ = ["CommandletRunnerPage"]
