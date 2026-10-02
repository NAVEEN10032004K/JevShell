"""Compatibility shim over the central safety engine.

Stage 2 kept the policy here. Stage 3 moved the decisions into jevsh/safety so
one engine serves both the shell and Jev. This module stays as the shell's view
of it: CommandEffect still describes what a command would touch, and check()
still answers the narrow question "is this line refused outright".
"""
from dataclasses import dataclass, field

from ..safety import evaluate
from ..safety.commands import Category, classify, path_operands
from ..safety.filesystem import canonicalize
from ..safety.result import SafetyLevel
from .ast import Pipeline, Redirection, SimpleCommand, walk_commands

# Kept for callers that only care whether a command removes things.
DESTRUCTIVE = {"rm", "rmdir", "mv", "dd", "shred", "truncate", "unlink"}


@dataclass
class CommandEffect:
    """What one command would touch, before it runs."""

    argv: list[str]
    reads: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    destructive: bool = False

    @property
    def name(self) -> str:
        return self.argv[0] if self.argv else ""


def describe(node, session) -> list[CommandEffect]:
    """One effect per command in the tree, with paths made absolute."""
    effects = []

    for command in walk_commands(node):
        if not command.argv and not command.redirections:
            continue

        effect = CommandEffect(
            argv=list(command.argv),
            destructive=classify(command.argv) is Category.FILESYSTEM_DELETE,
        )

        for redirection in command.redirections:
            target = str(canonicalize(redirection.target, session.cwd, session.environment))

            if redirection.writes:
                effect.writes.append(target)
            else:
                effect.reads.append(target)

        effects.append(effect)

    return effects


def targets_of(effect: CommandEffect, session) -> list[str]:
    """Path-like arguments of a destructive command, as absolute paths."""
    return [
        str(canonicalize(operand, session.cwd, session.environment))
        for operand in path_operands(effect.argv)
    ]


def check(effects, session) -> str | None:
    """The refusal message for a blocked command, or None.

    Takes effects for backwards compatibility with callers written before the
    safety engine returned a structured result. Each effect is evaluated as the
    command it describes, so there is still exactly one place that decides.
    """
    for effect in effects:
        command = SimpleCommand(argv=list(effect.argv))

        for target in effect.writes:
            command.redirections.append(Redirection(1, ">", target))

        result = evaluate(Pipeline([command]), session)

        if result.level is SafetyLevel.BLOCK:
            # Stage 2 phrased refusals in lower case; keep that for its callers.
            reason = result.reason
            return f"jevsh: blocked: {reason[:1].lower()}{reason[1:]}"

    return None
