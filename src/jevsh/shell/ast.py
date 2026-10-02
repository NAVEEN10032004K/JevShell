"""The command tree the parser builds and the executor walks.

Nothing here executes anything, and nothing here knows about subprocesses. That
separation is the point: the policy layer gets to inspect a whole command tree,
redirections and all, before a single process is spawned.

Named ast.py to match the project layout. The stdlib `ast` is not shadowed for
anyone else, because this package imports it relatively.
"""
from dataclasses import dataclass, field


@dataclass
class Redirection:
    """`> file`, `>> file` or `< file`.

    fd is kept even though only the defaults are supported, so the parser can
    recognize `2>` and reject it explicitly rather than silently misreading it.
    """

    fd: int
    operator: str
    target: str

    @property
    def writes(self) -> bool:
        return self.operator in (">", ">>")


@dataclass
class SimpleCommand:
    argv: list[str] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)

    def redirect(self, *operators: str) -> Redirection | None:
        """The last redirection matching any of these operators, as a shell uses."""
        found = [r for r in self.redirections if r.operator in operators]
        return found[-1] if found else None


@dataclass
class Pipeline:
    """One or more commands joined by `|`. A lone command is a pipeline of one."""

    commands: list[SimpleCommand] = field(default_factory=list)


@dataclass
class AndOr:
    """Pipelines joined by `&&` / `||`.

    operators[i] joins pipelines[i] to pipelines[i + 1], so there is always one
    fewer operator than pipeline.
    """

    pipelines: list[Pipeline] = field(default_factory=list)
    operators: list[str] = field(default_factory=list)


@dataclass
class SequenceItem:
    node: AndOr
    background: bool = False


@dataclass
class Sequence:
    """The whole line: items separated by `;` or `&`."""

    items: list[SequenceItem] = field(default_factory=list)


def walk_commands(node) -> list[SimpleCommand]:
    """Every SimpleCommand in the tree, in source order.

    The policy layer relies on this: a command must be inspectable no matter how
    deeply it is buried under operators.
    """
    if isinstance(node, SimpleCommand):
        return [node]

    if isinstance(node, Pipeline):
        return list(node.commands)

    if isinstance(node, AndOr):
        return [c for p in node.pipelines for c in walk_commands(p)]

    if isinstance(node, SequenceItem):
        return walk_commands(node.node)

    if isinstance(node, Sequence):
        return [c for item in node.items for c in walk_commands(item)]

    return []
