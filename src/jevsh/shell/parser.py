"""Scan a line into words and operators, then parse it into a command tree.

Stage 1 used shlex.split. That had to go: shlex discards *which* parts of a word
were quoted, so `'$HOME'` and `"$HOME"` come out identical and single quotes
cannot suppress expansion. A word here is therefore a list of (text, quote)
segments, and expansion and globbing consult the quoting of each segment.

Note this is the *shell* parser. jevsh/parser.py parses Jev responses and is
unrelated.
"""
import glob as globlib
from dataclasses import dataclass, field

from .ast import AndOr, Pipeline, Redirection, Sequence, SequenceItem, SimpleCommand
from .environment import apply_tilde, substitute

NONE, SINGLE, DOUBLE = "none", "single", "double"

OPERATORS = ("&&", "||", ">>", "|", "&", ";", "<", ">")
OPERATOR_START = set("&|;<>")
GLOB_CHARACTERS = set("*?[")


class ParseError(Exception):
    """The line could not be parsed, e.g. an unclosed quote or a stray operator."""


@dataclass
class Word:
    """One command-line word, kept as segments so quoting survives expansion."""

    segments: list[tuple[str, str]] = field(default_factory=list)

    def add(self, text: str, quote: str) -> None:
        """Append text, merging into the previous segment if it was quoted alike.

        Merging matters: unquoted input arrives one character at a time, and
        `$HOME` only expands if those characters end up in a single segment.
        """
        if not text:
            return

        if self.segments and self.segments[-1][1] == quote:
            previous, _ = self.segments[-1]
            self.segments[-1] = (previous + text, quote)
            return

        self.segments.append((text, quote))

    @property
    def empty(self) -> bool:
        return not self.segments

    def text(self) -> str:
        return "".join(text for text, _ in self.segments)


@dataclass
class Operator:
    value: str
    fd: int | None = None


def scan(line: str) -> list[Word | Operator]:
    """Split a line into Word and Operator tokens, preserving quote provenance."""
    tokens: list[Word | Operator] = []
    word = Word()
    index = 0
    # A word only exists once something was written into it; `""` is an empty
    # word that must survive, hence this flag rather than checking `segments`.
    started = False

    def flush():
        nonlocal word, started
        if started:
            tokens.append(word)
        word = Word()
        started = False

    while index < len(line):
        char = line[index]

        if char in " \t":
            flush()
            index += 1
            continue

        if char == "'":
            end = line.find("'", index + 1)
            if end == -1:
                raise ParseError("jevsh: syntax error: unterminated single quote")
            word.add(line[index + 1 : end], SINGLE)
            started = True
            index = end + 1
            continue

        if char == '"':
            index += 1
            buffer = []
            while index < len(line) and line[index] != '"':
                if line[index] == "\\" and index + 1 < len(line) and line[index + 1] in '"\\$`':
                    buffer.append(line[index + 1])
                    index += 2
                    continue
                buffer.append(line[index])
                index += 1

            if index >= len(line):
                raise ParseError("jevsh: syntax error: unterminated double quote")

            word.add("".join(buffer), DOUBLE)
            started = True
            index += 1
            continue

        if char == "\\" and index + 1 < len(line):
            # Escaped characters are marked single-quoted so neither variable
            # expansion nor globbing touches them.
            word.add(line[index + 1], SINGLE)
            started = True
            index += 2
            continue

        if char in OPERATOR_START:
            fd = None

            # A bare run of digits glued to a redirection is an fd prefix, e.g.
            # `2>`. Recognized so it can be rejected by name rather than being
            # silently misread as an argument followed by a redirect.
            if char in "<>" and started and len(word.segments) == 1:
                text, quote = word.segments[0]
                if quote == NONE and text.isdigit():
                    fd = int(text)
                    word = Word()
                    started = False

            flush()

            for operator in OPERATORS:
                if line.startswith(operator, index):
                    tokens.append(Operator(operator, fd))
                    index += len(operator)
                    break

            continue

        word.add(char, NONE)
        started = True
        index += 1

    flush()

    return tokens


def expand_word(word: Word, env: dict[str, str] | None, cwd=None) -> list[str]:
    """Expand one word into zero or more argv entries.

    Order matters and mirrors sh: variables, then tilde, then globbing. A single
    quoted segment is immune to all three.
    """
    if env is None:
        return [word.text()]

    expanded: list[tuple[str, str]] = []

    for text, quote in word.segments:
        if quote != SINGLE:
            text = substitute(text, env)
        expanded.append((text, quote))

    if expanded and expanded[0][1] == NONE:
        text, quote = expanded[0]
        expanded[0] = (apply_tilde(text, env), quote)

    literal = "".join(text for text, _ in expanded)

    if cwd is None:
        return [literal]

    # Only an unquoted metacharacter makes this a pattern. Quoted segments are
    # escaped so `"*.py"` matches a file literally named *.py, never every .py.
    has_pattern = any(
        quote == NONE and set(text) & GLOB_CHARACTERS for text, quote in expanded
    )

    if not has_pattern:
        return [literal]

    pattern = "".join(
        text if quote == NONE else globlib.escape(text) for text, quote in expanded
    )
    matches = sorted(globlib.glob(pattern, root_dir=cwd))

    # No match leaves the pattern alone, which is what a shell does with
    # nullglob off.
    return matches or [literal]


# Only the default descriptors are in scope: stdin for `<`, stdout for `>`/`>>`.
DEFAULT_FD = {"<": 0, ">": 1, ">>": 1}


def parse(line, *, env=None, cwd=None, aliases=None) -> Sequence:
    """Parse a line into a Sequence.

    Expansion and alias resolution happen here rather than during execution, so
    the tree handed to the policy layer holds real commands and real paths.

    Grammar, lowest precedence last:
        sequence := andor ((';' | '&') andor?)*
        andor    := pipeline (('&&' | '||') pipeline)*
        pipeline := command ('|' command)*
        command  := (word | redirection)+
    """
    from .aliases import expand as expand_aliases

    tokens = scan(line)
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else None

    def parse_command() -> SimpleCommand:
        nonlocal position
        command = SimpleCommand()

        while position < len(tokens):
            token = tokens[position]

            if isinstance(token, Word):
                command.argv.extend(expand_word(token, env, cwd))
                position += 1
                continue

            if token.value in ("<", ">", ">>"):
                operator = token.value
                fd = token.fd if token.fd is not None else DEFAULT_FD[operator]

                if fd != DEFAULT_FD[operator]:
                    raise ParseError(
                        f"jevsh: syntax error: file descriptor redirection "
                        f"`{fd}{operator}' is not supported"
                    )

                position += 1
                target = peek()

                if not isinstance(target, Word):
                    raise ParseError(
                        f"jevsh: syntax error near unexpected token `{operator}'"
                    )

                # A redirection target is expanded but never globbed: a shell
                # treats a pattern matching several files there as an error, and
                # we simply take it literally.
                names = expand_word(target, env, None)
                command.redirections.append(Redirection(fd, operator, names[0]))
                position += 1
                continue

            break

        if command.argv and aliases:
            command.argv = expand_aliases(
                command.argv,
                aliases,
                lambda body: [
                    name
                    for token in scan(body)
                    if isinstance(token, Word)
                    for name in expand_word(token, env, cwd)
                ],
            )

        return command

    def parse_pipeline() -> Pipeline:
        nonlocal position
        pipeline = Pipeline([parse_command()])

        while isinstance(peek(), Operator) and peek().value == "|":
            position += 1
            command = parse_command()

            if not command.argv and not command.redirections:
                raise ParseError("jevsh: syntax error near unexpected token `|'")

            pipeline.commands.append(command)

        return pipeline

    def parse_andor() -> AndOr:
        nonlocal position
        node = AndOr([parse_pipeline()], [])

        while isinstance(peek(), Operator) and peek().value in ("&&", "||"):
            operator = peek().value
            position += 1
            node.operators.append(operator)
            node.pipelines.append(parse_pipeline())

        return node

    sequence = Sequence()

    while position < len(tokens):
        node = parse_andor()
        separator = peek()

        if isinstance(separator, Operator) and separator.value in (";", "&"):
            position += 1
        elif separator is not None:
            raise ParseError(
                f"jevsh: syntax error near unexpected token `{separator.value}'"
            )

        empty = all(
            not c.argv and not c.redirections
            for p in node.pipelines
            for c in p.commands
        )

        if not empty:
            background = isinstance(separator, Operator) and separator.value == "&"
            sequence.items.append(SequenceItem(node, background))

    return sequence


def tokenize(line: str, env: dict[str, str] | None = None) -> list[str]:
    """Expand a single command line into argv.

    Kept from Stage 1 for callers and tests that deal in one plain command. An
    operator belongs to parse(), so finding one here is an error.
    """
    argv = []

    for token in scan(line):
        if isinstance(token, Operator):
            raise ParseError(
                f"jevsh: syntax error near unexpected token `{token.value}'"
            )

        argv.extend(expand_word(token, env))

    return argv
