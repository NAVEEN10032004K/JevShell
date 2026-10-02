"""Settings read from the environment.

No config file and no stored secrets. The API key is read where it is used, in
jev.py, and never copied here -- a settings object that holds a credential is a
settings object that eventually gets logged.
"""
import logging
import os
import sys

LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def _disabled(name: str) -> bool:
    """True when an environment variable is set to an off-ish value."""
    value = os.environ.get(name)

    return value is not None and value.strip().lower() in {"0", "false", "no", "off"}


def jev_enabled() -> bool:
    """False turns natural language off entirely; nothing reaches the network."""
    return not _disabled("JEVSH_JEV_ENABLED")


def color_enabled(stream=None) -> bool:
    """Color only for a real terminal, and only when nobody asked us not to.

    NO_COLOR is honoured whenever it is set at all, however it is set, which is
    what the convention asks for.
    """
    if "NO_COLOR" in os.environ or "JEVSH_NO_COLOR" in os.environ:
        return False

    stream = stream or sys.stdout

    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def configure_logging() -> None:
    """Quiet unless JEVSH_LOG_LEVEL asks otherwise. Logs go to stderr.

    The level is set explicitly rather than through basicConfig alone, because
    basicConfig does nothing once the root logger already has a handler -- which
    would make JEVSH_LOG_LEVEL silently ineffective under any host that
    configures logging first.
    """
    requested = os.environ.get("JEVSH_LOG_LEVEL", "").strip().upper()
    level = getattr(logging, requested) if requested in LOG_LEVELS else logging.WARNING

    root = logging.getLogger()

    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("jevsh %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)

    root.setLevel(level)
