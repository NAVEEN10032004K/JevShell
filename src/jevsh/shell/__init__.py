"""The shell foundation: session, parser, command IR, policy, executor, REPL.

Separate from the Jev layer in the parent package by design.
"""
from .aliases import AliasError
from .ast import AndOr, Pipeline, Redirection, Sequence, SequenceItem, SimpleCommand
from .builtins import BUILTINS, ExitShell
from .executor import execute, run_external
from .jobs import Job
from .parser import ParseError, parse, scan, tokenize
from .policy import CommandEffect
from .repl import dispatch, run_repl
from .session import ShellSession

__all__ = [
    "AliasError",
    "AndOr",
    "BUILTINS",
    "CommandEffect",
    "ExitShell",
    "Job",
    "ParseError",
    "Pipeline",
    "Redirection",
    "Sequence",
    "SequenceItem",
    "ShellSession",
    "SimpleCommand",
    "dispatch",
    "execute",
    "parse",
    "run_external",
    "run_repl",
    "scan",
    "tokenize",
]
