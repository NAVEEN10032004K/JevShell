"""How JevShell talks to the user.

All the operator-facing blocks live here so the wording stays consistent and so
the executor and REPL do not each grow their own formatting.
"""
from . import config

RESET = "\033[0m"
CODES = {"red": "\033[31m", "yellow": "\033[33m", "green": "\033[32m", "dim": "\033[2m"}


def paint(text: str, color: str) -> str:
    """Wrap text in a color, or return it untouched when color is off.

    Checked per call rather than cached, so a test or a pipe changing the
    environment takes effect immediately.
    """
    if not config.color_enabled():
        return text

    return f"{CODES.get(color, '')}{text}{RESET}"


def blocked(reason: str) -> str:
    """A refusal. Never offers a choice: BLOCK means it will not run."""
    return f"{paint('Command blocked:', 'red')}\n    {reason}"


def confirmation(result) -> str:
    """The prompt body for a CONFIRM, shown before asking."""
    lines = [
        "",
        paint("This command requires confirmation:", "yellow"),
        f"    {result.describe()}",
        "",
        "Reason:",
        f"    {result.reason}",
        "",
    ]

    return "\n".join(lines)


def jev_preview(intent) -> str:
    """What Jev understood, before anything is run."""
    lines = ["", paint("Jev:", "dim"), f"  Intent: {intent.description}"]

    if intent.shown_target:
        lines.append(f"  Target: {intent.shown_target}")

    lines.append("")

    return "\n".join(lines)


def error(message: str) -> str:
    return paint(message, "red")
