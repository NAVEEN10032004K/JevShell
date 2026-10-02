"""The scanner: quote provenance, operators, and what must be rejected."""
import pytest

from jevsh.shell.parser import DOUBLE, NONE, SINGLE, Operator, ParseError, Word, scan, tokenize

ENV = {"HOME": "/session/home", "NAME": "naveen"}


def kinds(line):
    return [t.value if isinstance(t, Operator) else t.text() for t in scan(line)]


def test_single_quotes_suppress_expansion():
    # The whole reason shlex.split had to go: it could not tell these apart.
    assert tokenize("echo '$NAME'", ENV) == ["echo", "$NAME"]


def test_double_quotes_allow_expansion():
    assert tokenize('echo "$NAME"', ENV) == ["echo", "naveen"]
    assert tokenize('echo "Home: $HOME"', ENV) == ["echo", "Home: /session/home"]


def test_quote_styles_are_distinguishable():
    assert tokenize("echo '$NAME'", ENV) != tokenize('echo "$NAME"', ENV)


def test_mixed_quoting_in_one_word():
    assert tokenize('echo --name="$NAME"', ENV) == ["echo", "--name=naveen"]
    assert tokenize("""echo '$NAME'"$NAME\"""", ENV) == ["echo", "$NAMEnaveen"]


def test_segments_record_their_quoting():
    word = scan("""a'b'"c\"""")[0]
    assert word.segments == [("a", NONE), ("b", SINGLE), ("c", DOUBLE)]


def test_backslash_escapes_a_dollar():
    assert tokenize(r"echo \$NAME", ENV) == ["echo", "$NAME"]


def test_empty_quoted_word_survives():
    assert tokenize('echo ""') == ["echo", ""]


def test_operators_are_separate_tokens():
    assert kinds("a | b") == ["a", "|", "b"]
    assert kinds("a && b") == ["a", "&&", "b"]
    assert kinds("a || b") == ["a", "||", "b"]
    assert kinds("a ; b") == ["a", ";", "b"]
    assert kinds("a &") == ["a", "&"]
    assert kinds("a > f") == ["a", ">", "f"]
    assert kinds("a >> f") == ["a", ">>", "f"]
    assert kinds("a < f") == ["a", "<", "f"]


def test_operators_without_surrounding_spaces():
    assert kinds("echo hi>f") == ["echo", "hi", ">", "f"]
    assert kinds("a|b") == ["a", "|", "b"]
    assert kinds("a>>f") == ["a", ">>", "f"]


def test_longest_operator_wins():
    assert kinds("a>>b") == ["a", ">>", "b"]
    assert kinds("a&&b") == ["a", "&&", "b"]


def test_operators_inside_quotes_are_literal():
    assert tokenize('echo "a | b"') == ["echo", "a | b"]
    assert tokenize("echo 'a && b'") == ["echo", "a && b"]


def test_unterminated_quotes_raise():
    with pytest.raises(ParseError):
        tokenize('echo "unclosed')

    with pytest.raises(ParseError):
        tokenize("echo 'unclosed")


def test_tokenize_rejects_operators():
    # tokenize() handles one plain command; operators belong to parse().
    with pytest.raises(ParseError):
        tokenize("ls | grep py")
