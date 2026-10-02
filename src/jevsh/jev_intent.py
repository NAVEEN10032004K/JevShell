"""What Jev decided, and how that becomes an ordinary shell command.

Jev's answer is a choice from a fixed set of five, so an intent can only ever
name one of five operations. Nothing here holds a shell string: the model picks
an operation, deterministic code picks the path, and this module assembles argv.
That is why no model output can become a command.
"""
from dataclasses import dataclass
from pathlib import Path

from .models import ActionType
from .shell.ast import SimpleCommand

# Measured against the live API rather than guessed. Every one of the intended
# phrasings scored 1.00; genuinely ambiguous input fell to 0.73 and 0.66.
#
# Treat this as a disagreement measure, not a correctness score. "sort this out"
# scored 0.91 for ls, so a high number means the options were well separated, not
# that the request made sense. The safety layer is the real guard.
CONFIRM_THRESHOLD = 0.90

# What each intent is called when talking to the user.
DESCRIPTIONS = {
    ActionType.MKDIR: "create directory",
    ActionType.TOUCH: "create file",
    ActionType.LS: "list files",
    ActionType.PWD: "show current directory",
    ActionType.DELETE: "delete",
}

# Intents that cannot do anything without knowing what to act on.
NEEDS_TARGET = {ActionType.MKDIR, ActionType.TOUCH, ActionType.DELETE}

# Intents a target means anything to. pwd ignores one, so a stray word picked up
# by the extractor must not be shown to the user as if it mattered.
USES_TARGET = NEEDS_TARGET | {ActionType.LS}

CLARIFICATIONS = [
    (ActionType.MKDIR, "create a directory"),
    (ActionType.TOUCH, "create a file"),
    (ActionType.LS, "list files"),
]


class IntentError(Exception):
    """The intent cannot be turned into a command, with a reason for the user."""


@dataclass
class JevIntent:
    action: ActionType
    confidence: float
    target: str | None = None
    raw_input: str = ""

    @property
    def description(self) -> str:
        return DESCRIPTIONS.get(self.action, self.action.value)

    @property
    def is_confident(self) -> bool:
        return self.confidence >= CONFIRM_THRESHOLD

    @property
    def needs_target(self) -> bool:
        return self.action in NEEDS_TARGET and not self.target

    @property
    def shown_target(self) -> str | None:
        """The target worth reporting, or None when the intent ignores it."""
        return self.target if self.action in USES_TARGET else None


def from_response(response: dict, user_input: str, target: str | None = None) -> JevIntent:
    """Build an intent from a Jev reply.

    A choice outside the schema raises ValueError from the enum lookup, which is
    the mechanism that stops unexpected model text from ever reaching argv.
    """
    answer = response["answers"]["decision"]

    return JevIntent(
        action=ActionType(answer["choice"]),
        confidence=float(answer.get("confidence", 0.0)),
        target=target,
        raw_input=user_input,
    )


def to_command(intent: JevIntent, session) -> SimpleCommand:
    """Turn an intent into the same SimpleCommand a typed command would produce.

    Raises IntentError rather than inventing a path when the target is missing.
    """
    if intent.needs_target:
        raise IntentError(
            f"I understand that you want to {intent.description}, "
            "but I need the path."
        )

    if intent.action is ActionType.PWD:
        return SimpleCommand(argv=["pwd"])

    if intent.action is ActionType.LS:
        return SimpleCommand(argv=["ls", intent.target] if intent.target else ["ls"])

    if intent.action is ActionType.MKDIR:
        return SimpleCommand(argv=["mkdir", intent.target])

    if intent.action is ActionType.TOUCH:
        return SimpleCommand(argv=["touch", intent.target])

    if intent.action is ActionType.DELETE:
        argv = ["rm"]

        # A directory needs -r, a file must not get it. Decided here by looking
        # at the filesystem, never by the model.
        if _is_directory(intent.target, session):
            argv.append("-r")

        argv.append(intent.target)

        return SimpleCommand(argv=argv)

    raise IntentError(f"Unsupported intent: {intent.action}")


def _is_directory(target: str, session) -> bool:
    try:
        path = Path(target).expanduser()

        if not path.is_absolute():
            path = Path(session.cwd) / path

        return path.is_dir()
    except OSError:
        return False


def clarification(intent: JevIntent) -> str:
    """The numbered question asked when confidence is too low to act on."""
    lines = [
        "I couldn't determine the filesystem operation.",
        "",
        "Did you want to:",
    ]

    for number, (_, text) in enumerate(CLARIFICATIONS, start=1):
        lines.append(f"  {number}. {text}")

    lines.append("")
    lines.append("Rephrase your request, or use a normal shell command.")

    return "\n".join(lines)
