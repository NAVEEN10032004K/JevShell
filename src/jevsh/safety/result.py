"""The decision a safety check returns.

Callers branch on a level and print a reason; nobody has to interpret a string.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class SafetyLevel(Enum):
    """How jevsh should treat a command.

    SAFE and BLOCKED are aliases of ALLOW and BLOCK rather than separate members.
    The Jev layer has used the older names since Stage 1, and aliasing lets both
    spellings refer to the same member instead of forcing a rename across the
    project: SafetyLevel.SAFE is SafetyLevel.ALLOW.
    """

    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"

    SAFE = "allow"
    BLOCKED = "block"

    @property
    def severity(self) -> int:
        return {"allow": 0, "confirm": 1, "block": 2}[self.value]

    def __lt__(self, other) -> bool:
        if not isinstance(other, SafetyLevel):
            return NotImplemented
        return self.severity < other.severity


@dataclass
class SafetyResult:
    """One finding: what level, why, and which command and path caused it."""

    level: SafetyLevel
    reason: str
    command: str | None = None
    path: Path | None = None

    @property
    def allowed(self) -> bool:
        return self.level is SafetyLevel.ALLOW

    @property
    def blocked(self) -> bool:
        return self.level is SafetyLevel.BLOCK

    def describe(self) -> str:
        """The command as the policy engine saw it, for messages to the user."""
        return self.command or "(command)"


ALLOWED = SafetyResult(SafetyLevel.ALLOW, "No policy concerns.")


def most_severe(results: list[SafetyResult]) -> SafetyResult:
    """The worst finding, which is what decides whether a line may run."""
    return max(results, key=lambda r: r.level.severity) if results else ALLOWED
