import pytest

from jevsh.shell.parser import ParseError, tokenize


def test_flags_are_separate_tokens():
    assert tokenize("ls -lah") == ["ls", "-lah"]


def test_quoted_argument_stays_one_token():
    assert tokenize('echo "hello world"') == ["echo", "hello world"]
    assert tokenize('mkdir "my project"') == ["mkdir", "my project"]
    assert tokenize('cat "hello world.txt"') == ["cat", "hello world.txt"]


def test_quoted_value_after_flag():
    assert tokenize('python script.py --name "Naveen"') == [
        "python",
        "script.py",
        "--name",
        "Naveen",
    ]


def test_naive_split_would_be_wrong():
    # The reason shlex is used at all.
    line = 'echo "hello world"'
    assert tokenize(line) != line.split(" ")


def test_variable_expansion_uses_supplied_env():
    env = {"HOME": "/session/home", "NAME": "naveen"}

    assert tokenize("echo $HOME", env) == ["echo", "/session/home"]
    assert tokenize("echo ${NAME}", env) == ["echo", "naveen"]
    assert tokenize("echo a${NAME}b", env) == ["echo", "anaveenb"]


def test_unset_variable_becomes_empty_like_sh():
    assert tokenize("echo $NOPE", {}) == ["echo", ""]


def test_tilde_expands_from_session_home():
    env = {"HOME": "/session/home"}

    assert tokenize("cd ~", env) == ["cd", "/session/home"]
    assert tokenize("cat ~/notes.txt", env) == ["cat", "/session/home/notes.txt"]
    # A bare ~ prefix on an unrelated word is not a home reference.
    assert tokenize("echo ~user", env) == ["echo", "~user"]


def test_empty_input():
    assert tokenize("") == []
    assert tokenize("   ") == []


def test_unclosed_quote_raises_parse_error():
    with pytest.raises(ParseError):
        tokenize('echo "unclosed')
