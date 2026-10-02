"""Alias storage, expansion and the alias/unalias builtins.

Expansion runs at parse time, not execution time. That matters for safety: if
`alias del="rm -rf"` were expanded by the executor, the command tree the policy
layer inspects would say `del` and the real `rm -rf` would never be classified.
Expanding first means policy always sees the actual command.
"""


class AliasError(Exception):
    """A cycle, e.g. alias a="b" with alias b="a"."""


def expand(words: list[str], aliases: dict[str, str], split) -> list[str]:
    """Replace a leading alias name with its body, repeatedly.

    `split` tokenizes an alias body into words; it is injected so this module
    does not import the parser and create a cycle between them.

    Only the command word expands, which is why `echo ll` keeps its argument
    intact. A name already expanded on this line is not expanded again, which
    terminates a->b->a instead of looping forever.
    """
    if not words:
        return words

    seen: set[str] = set()

    while words and words[0] in aliases:
        name = words[0]

        if name in seen:
            raise AliasError(f"jevsh: alias: cyclic alias chain for `{name}'")

        seen.add(name)
        body = split(aliases[name])

        if not body:
            return words[1:]

        words = body + words[1:]

        # A self-referential alias (alias ls="ls -l") expands once and stops,
        # the same escape hatch real shells use.
        if words[0] == name:
            break

    return words


def builtin_alias(args: list[str], session) -> int:
    if not args:
        for name in sorted(session.aliases):
            print(f"alias {name}='{session.aliases[name]}'")
        return 0

    status = 0

    for arg in args:
        name, separator, value = arg.partition("=")

        if not separator:
            if name in session.aliases:
                print(f"alias {name}='{session.aliases[name]}'")
            else:
                print(f"jevsh: alias: {name}: not found")
                status = 1
            continue

        if not name:
            print(f"jevsh: alias: `{arg}': invalid alias name")
            status = 1
            continue

        session.aliases[name] = value

    return status


def builtin_unalias(args: list[str], session) -> int:
    if not args:
        print("jevsh: unalias: usage: unalias name [name ...]")
        return 1

    status = 0

    for name in args:
        if session.aliases.pop(name, None) is None:
            print(f"jevsh: unalias: {name}: not found")
            status = 1

    return status
