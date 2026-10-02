"""Routing decides whether Jev is consulted at all, without a network call."""
from jevsh.jev_router import InputType, route_input, strip_prefix

SHELL, NL = InputType.SHELL, InputType.NATURAL_LANGUAGE


def test_ordinary_shell_commands_stay_shell(session):
    for line in (
        "pwd", "ls", "ls -lah", "cd project", "echo hello", "cat file.txt",
        "git status", "python --version", "mkdir projects", "touch notes.txt",
        "rm test.txt", "history", "export NAME=x", "jobs",
    ):
        assert route_input(line, session) is SHELL, line


def test_operators_mean_shell(session):
    for line in (
        'ls | grep ".py"', "echo hello > file.txt", "cat < file.txt",
        "mkdir a && cd a", "false || echo hi", "echo one ; echo two",
        "sleep 1 &", "echo $HOME", "ls *.py",
    ):
        assert route_input(line, session) is SHELL, line


def test_natural_language_routes_to_jev(session):
    for line in (
        "create a folder called projects",
        "make a file named notes.txt",
        "show me the current directory",
        "list the files here",
        "delete test.txt",
        "delete everything in my home directory",
    ):
        assert route_input(line, session) is NL, line


def test_explicit_prefix_always_routes_to_jev(session):
    assert route_input("ai create a folder called test", session) is NL
    assert route_input("ai pwd", session) is NL
    assert route_input("AI list the files", session) is NL


def test_strip_prefix_removes_only_the_prefix():
    assert strip_prefix("ai create a folder") == "create a folder"
    assert strip_prefix("create a folder") == "create a folder"
    # A command that merely starts with the letters a-i is untouched.
    assert strip_prefix("aiohttp --version") == "aiohttp --version"


def test_a_real_command_phrased_as_a_sentence(session):
    # make is a genuine binary, so only the English markers separate these.
    assert route_input("make an empty file called notes.txt", session) is NL
    assert route_input("make install", session) is SHELL
    assert route_input("make -j4", session) is SHELL
    assert route_input("make clean", session) is SHELL


def test_one_marker_is_not_enough(session):
    # "the" alone must not steal a legitimate grep.
    assert route_input("grep the pattern file.txt", session) is SHELL


def test_single_words_are_shell(session):
    for line in ("pwd", "ls", "clear", "exit", "nonexistentcommand"):
        assert route_input(line, session) is SHELL, line


def test_executable_paths_are_shell(session):
    assert route_input("./script.sh arg", session) is SHELL
    assert route_input("/bin/ls -la", session) is SHELL
    assert route_input("../tool run", session) is SHELL


def test_aliases_count_as_known_commands(session):
    # An alias is a real command; routing it to Jev would break it and would
    # hand the policy layer a different command than the user invoked.
    session.aliases["ll"] = "ls -lah"
    session.aliases["wipe"] = "rm -rf"

    assert route_input("ll /tmp", session) is SHELL
    assert route_input("wipe /tmp", session) is SHELL


def test_empty_input_is_shell(session):
    assert route_input("", session) is SHELL
    assert route_input("   ", session) is SHELL


def test_shell_commands_never_call_jev(session):
    # The autouse guard raises if the real client is reached, so simply
    # dispatching these proves no network call happens.
    from jevsh.shell.repl import dispatch

    for line in ("pwd", "echo hi", "ls"):
        dispatch(line, session)
