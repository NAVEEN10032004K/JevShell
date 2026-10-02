"""Decide whether a line is a shell command or a request for Jev.

Routing is deterministic and offline: no network call is made to find out what
kind of input this is. A typed shell command never costs an API round trip.

The load-bearing rule is that an unknown first word goes to Jev. If the word is
neither a builtin nor on PATH, the shell could only answer "command not found",
so handing it to Jev cannot steal a working command. Verified against this
machine: create, show, list, delete and remove are not binaries, while mkdir,
touch, pwd, ls, rm, cat, git and python all are.
"""
import logging
import os
import shutil
import time
from enum import Enum

import requests

from . import config, ui
from .extractor import extract_path
from .jev import JevError, ask_jev
from .jev_intent import IntentError, JevIntent, clarification, from_response, to_command
from .shell.ast import AndOr, Pipeline, Sequence, SequenceItem
from .shell.builtins import BUILTINS

PREFIX = "ai "

# Operators mean the user is writing shell, not English.
METACHARACTERS = set("|&;<>$*?=")

# Words that are ordinary in an English request and rare in a command line.
# Two of them are what separates "make an empty file called notes.txt" from
# "make install", while leaving "grep the pattern file.txt" alone.
MARKERS = {
    "a", "an", "the", "called", "named", "my", "me", "here", "this", "that",
    "everything", "empty", "folder", "directory", "file", "files", "please",
    "new", "inside", "into", "current", "show", "make", "create", "delete",
}

UNAVAILABLE = "Jev is unavailable.\nUse a normal shell command instead."

NO_KEY = (
    "Jev is unavailable.\n"
    "Set TYPESAFE_API_KEY to enable natural-language commands."
)

logger = logging.getLogger(__name__)


def has_api_key() -> bool:
    return bool(os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API"))


class InputType(Enum):
    SHELL = "shell"
    NATURAL_LANGUAGE = "natural_language"


def strip_prefix(text: str) -> str:
    """Remove an explicit `ai ` prefix, if present."""
    stripped = text.strip()

    if stripped.lower().startswith(PREFIX):
        return stripped[len(PREFIX):].strip()

    return stripped


def is_known_command(word: str, session=None) -> bool:
    """Builtin, alias, or something on PATH.

    Aliases count. An aliased name is a real shell command that would have run,
    so routing it to Jev would both break the alias and hand the policy layer a
    different command than the one the user invoked.
    """
    if word in BUILTINS:
        return True

    if session is not None and word in getattr(session, "aliases", {}):
        return True

    return shutil.which(word) is not None


def marker_count(words: list[str]) -> int:
    return sum(1 for word in words[1:] if word.strip(".,!?").lower() in MARKERS)


def route_input(text: str, session=None) -> InputType:
    """Classify one line. Anything unclear stays a shell command."""
    stripped = text.strip()

    if not stripped:
        return InputType.SHELL

    # An explicit prefix always wins, unless Jev is switched off entirely.
    if stripped.lower().startswith(PREFIX):
        return (
            InputType.NATURAL_LANGUAGE
            if config.jev_enabled()
            else InputType.SHELL
        )

    if not config.jev_enabled():
        return InputType.SHELL

    words = stripped.split()

    # One bare word is a command, not a sentence.
    if len(words) < 2:
        return InputType.SHELL

    if set(stripped) & METACHARACTERS:
        return InputType.SHELL

    first = words[0]

    # A path means the user is naming an executable.
    if "/" in first or first.startswith("."):
        return InputType.SHELL

    if is_known_command(first, session):
        # A real command, but phrased like a sentence. Two markers is the bar.
        return (
            InputType.NATURAL_LANGUAGE
            if marker_count(words) >= 2
            else InputType.SHELL
        )

    return InputType.NATURAL_LANGUAGE


def build_intent(line: str) -> JevIntent:
    """Ask Jev what the user wants, and extract the target deterministically.

    Only the user's own words are sent. No environment, no history, no key.
    """
    request = strip_prefix(line)

    started = time.monotonic()
    response = ask_jev(request)
    # Timing only. The request body, the headers and the key are never logged.
    logger.debug("jev request completed in %.0f ms", (time.monotonic() - started) * 1000)

    return from_response(response, request, extract_path(request))


def handle_natural_language(line: str, session) -> int:
    """Run one natural-language request through the ordinary shell machinery."""
    from .shell.executor import execute

    try:
        intent = build_intent(line)

    except (JevError, requests.RequestException, ValueError, KeyError, TypeError) as error:
        # The exception text is never shown: it can carry a URL, a header or the
        # key itself. Only the type reaches the debug log.
        logger.debug("jev request failed: %s", type(error).__name__)

        print(ui.error(UNAVAILABLE if has_api_key() else NO_KEY))
        return 1

    if not intent.is_confident:
        print(clarification(intent))
        return 1

    try:
        command = to_command(intent, session)
    except IntentError as error:
        print(error)
        return 1

    print(ui.jev_preview(intent))

    tree = Sequence([SequenceItem(AndOr([Pipeline([command])], []))])

    # The same executor, the same safety engine, the same confirmation prompt a
    # typed command gets. Jev has no say in any of it.
    return execute(tree, session, " ".join(command.argv))
