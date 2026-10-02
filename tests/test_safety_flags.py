"""Flags are parsed, not pattern-matched against one spelling."""
from pathlib import Path

from jevsh.safety import SafetyLevel
from jevsh.safety.commands import command_name, is_recursive, path_operands, split_options

ALLOW, CONFIRM, BLOCK = SafetyLevel.ALLOW, SafetyLevel.CONFIRM, SafetyLevel.BLOCK
HOME = str(Path.home())


def test_the_spec_table(level):
    assert level("rm file.txt") is CONFIRM
    assert level("rm -r project/") is CONFIRM
    assert level("rm -rf /") is BLOCK
    assert level("rm -rf ~") is BLOCK
    assert level("rm -rf ~/Documents") is CONFIRM


def test_every_recursive_spelling_is_understood():
    for argv in (
        ["rm", "-r", "x"], ["rm", "-R", "x"], ["rm", "-rf", "x"],
        ["rm", "-fr", "x"], ["rm", "--recursive", "x"], ["rm", "-f", "-r", "x"],
        ["rm", "-vrf", "x"],
    ):
        assert is_recursive(argv), argv


def test_non_recursive_spellings():
    for argv in (["rm", "x"], ["rm", "-f", "x"], ["rm", "-i", "x"], ["rm", "--force", "x"]):
        assert not is_recursive(argv), argv


def test_flag_order_does_not_matter(level):
    for line in ("rm -rf /", "rm -fr /", "rm -f -r /", "rm -r -f /", "rm --recursive --force /"):
        assert level(line) is BLOCK, line


def test_absolute_executable_path_is_classified_the_same(level):
    assert level("/bin/rm -rf /") is BLOCK
    assert level("/usr/bin/env") is ALLOW
    assert command_name(["/bin/rm"]) == "rm"


def test_double_dash_terminates_options():
    options, operands = split_options(["rm", "-rf", "--", "-weird-name"])

    assert options == ["-rf"]
    assert operands == ["-weird-name"]


def test_options_are_not_treated_as_paths():
    assert path_operands(["rm", "-rf", "project"]) == ["project"]
    assert path_operands(["chmod", "-R", "755", "dir"]) == ["755", "dir"]


def test_recursion_is_mentioned_in_the_reason(session):
    from jevsh.safety import evaluate
    from jevsh.shell.parser import parse

    tree = parse("rm -rf project", env=session.environment, cwd=session.cwd)
    result = evaluate(tree, session)

    assert "ecursiv" in result.reason


def test_recursion_alone_does_not_block(level):
    # -rf is only fatal when pointed at something protected.
    assert level("rm -rf build/") is CONFIRM
    assert level("rm -rf ./node_modules") is CONFIRM


def test_home_subdirectories_confirm_but_do_not_block(level):
    assert level(f"rm -rf {HOME}/Documents") is CONFIRM
    assert level(f"rm -rf {HOME}/Desktop/project") is CONFIRM
