"""The one deterministic safety engine.

Two entry points live here on purpose, so it is visible that both callers reach
the same filesystem rules and neither can route around them:

    evaluate(node, session)   a parsed shell command tree

Natural language reaches this same function: Jev's intent is converted into a
SimpleCommand before it gets here, so an AI-proposed action is judged by exactly
the rules a typed one is.

Nothing here calls Jev, and nothing here runs a command to find out whether it is
safe. Jev may propose an action; it may not authorize one.
"""
from . import commands as cmd
from .filesystem import canonicalize, is_protected, is_system
from .result import ALLOWED, SafetyLevel, SafetyResult, most_severe

DESTRUCTIVE_CATEGORIES = {
    cmd.Category.FILESYSTEM_DELETE,
    cmd.Category.SYSTEM_CONFIGURATION,
    cmd.Category.PROCESS_CONTROL,
}

CONFIRM_REASONS = {
    cmd.Category.FILESYSTEM_DELETE: "Deletes or moves files.",
    cmd.Category.SYSTEM_CONFIGURATION: "Changes system or file configuration.",
    cmd.Category.PROCESS_CONTROL: "Signals or reprioritizes a running process.",
}


def _write_targets(command, session) -> list:
    """Redirection targets that would be created or truncated."""
    return [
        canonicalize(r.target, session.cwd, session.environment)
        for r in command.redirections
        if r.writes
    ]


def _delete_targets(command, session) -> list:
    """Paths a destructive command would act on."""
    return [
        canonicalize(operand, session.cwd, session.environment)
        for operand in cmd.path_operands(command.argv)
    ]


def _refuse(path, name, verb, env=None) -> SafetyResult | None:
    """BLOCK if this path must never be written to or deleted."""
    if is_protected(path, env):
        if path == path.parent:
            detail = "the filesystem root"
        else:
            detail = f"{path}"
        return SafetyResult(
            SafetyLevel.BLOCK,
            f"Refusing to {verb} {detail}.",
            command=name,
            path=path,
        )

    if is_system(path):
        return SafetyResult(
            SafetyLevel.BLOCK,
            f"Refusing to {verb} the protected system path {path}.",
            command=name,
            path=path,
        )

    return None


def evaluate_command(command, session) -> SafetyResult:
    """Judge one SimpleCommand."""
    if not command.argv and not command.redirections:
        return ALLOWED

    name = cmd.command_name(command.argv)
    text = " ".join(command.argv) or "(redirection)"
    category = cmd.classify(command.argv)
    findings = []

    # Redirection is a filesystem write in its own right, whatever the command.
    for target in _write_targets(command, session):
        refusal = _refuse(target, text, "write", session.environment)
        if refusal:
            findings.append(refusal)

    # A clobbering write still has to clear the protected-path rules. Only the
    # last operand is the destination; everything before it is a source being
    # read, which is harmless.
    if cmd.overwrites(command.argv):
        destinations = _delete_targets(command, session)[-1:]

        for target in destinations:
            refusal = _refuse(target, text, "overwrite", session.environment)
            if refusal:
                findings.append(refusal)

        if not findings:
            findings.append(
                SafetyResult(
                    SafetyLevel.CONFIRM,
                    "Overwrites the destination if it already exists.",
                    command=text,
                )
            )

    if category in DESTRUCTIVE_CATEGORIES:
        verb = "delete" if category is cmd.Category.FILESYSTEM_DELETE else "modify"

        for target in _delete_targets(command, session):
            refusal = _refuse(target, text, verb, session.environment)
            if refusal:
                findings.append(refusal)

        if not findings:
            reason = CONFIRM_REASONS[category]

            if cmd.is_recursive(command.argv):
                reason = f"Recursively deletes a directory tree. {reason}"

            findings.append(
                SafetyResult(SafetyLevel.CONFIRM, reason, command=text)
            )

    if not findings:
        return SafetyResult(SafetyLevel.ALLOW, "No policy concerns.", command=text)

    return most_severe(findings)


def evaluate_all(node, session) -> list[SafetyResult]:
    """Every finding in the tree.

    walk_commands reaches every SimpleCommand under pipes, &&, ||, ; and &, so a
    dangerous command cannot hide behind a safe one or behind an operator.

    Imported here rather than at module scope to keep the dependency one-way:
    the shell imports safety, so safety must not import the shell package while
    it is still initializing.
    """
    from ..shell.ast import walk_commands

    return [evaluate_command(command, session) for command in walk_commands(node)]


def evaluate(node, session) -> SafetyResult:
    """The decision for a whole line: its most severe finding."""
    findings = [r for r in evaluate_all(node, session) if r.level is not SafetyLevel.ALLOW]

    if not findings:
        return ALLOWED

    return most_severe(findings)
