"""JevShell's deterministic safety layer.

One engine, one entry point. Every command reaches `evaluate()` as a parsed
command tree -- typed by the user or converted from a Jev intent, the rules are
the same either way.
"""
from .commands import Category, classify, command_name, is_recursive, path_operands
from .filesystem import (
    SYSTEM_PATHS,
    TEMP_PATHS,
    canonicalize,
    is_protected,
    is_protected_path,
    is_system,
    is_temp,
)
from .policy import evaluate, evaluate_all, evaluate_command
from .result import ALLOWED, SafetyLevel, SafetyResult, most_severe

__all__ = [
    "ALLOWED",
    "Category",
    "SYSTEM_PATHS",
    "SafetyLevel",
    "SafetyResult",
    "TEMP_PATHS",
    "canonicalize",
    "classify",
    "command_name",
    "evaluate",
    "evaluate_all",
    "evaluate_command",
    "is_protected",
    "is_protected_path",
    "is_recursive",
    "is_system",
    "is_temp",
    "most_severe",
    "path_operands",
]
