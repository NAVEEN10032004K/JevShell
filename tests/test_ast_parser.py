"""Parsing into the IR: precedence, redirection placement, background."""
import pytest

from jevsh.shell.parser import ParseError, parse


def argvs(tree):
    return [
        [c.argv for c in p.commands]
        for item in tree.items
        for p in item.node.pipelines
    ]


def test_simple_command():
    tree = parse("ls -lah")
    assert len(tree.items) == 1
    assert argvs(tree) == [[["ls", "-lah"]]]


def test_pipeline_of_two():
    tree = parse("ls | grep py")
    assert argvs(tree) == [[["ls"], ["grep", "py"]]]


def test_pipeline_of_arbitrary_length():
    tree = parse("a | b | c | d")
    pipeline = tree.items[0].node.pipelines[0]
    assert [c.argv[0] for c in pipeline.commands] == ["a", "b", "c", "d"]


def test_redirection_binds_to_its_own_command():
    # `ls | grep py > out` redirects grep, not ls -- redirection binds tighter
    # than the pipe.
    tree = parse("ls | grep py > result.txt")
    commands = tree.items[0].node.pipelines[0].commands

    assert commands[0].redirections == []
    assert commands[1].redirections[0].operator == ">"
    assert commands[1].redirections[0].target == "result.txt"
    assert commands[1].argv == ["grep", "py"]


def test_input_and_output_redirection_on_one_command():
    command = parse("sort < in.txt > out.txt").items[0].node.pipelines[0].commands[0]
    operators = {r.operator: r.target for r in command.redirections}

    assert operators == {"<": "in.txt", ">": "out.txt"}


def test_redirection_before_arguments():
    command = parse("> out.txt echo hi").items[0].node.pipelines[0].commands[0]

    assert command.argv == ["echo", "hi"]
    assert command.redirections[0].target == "out.txt"


def test_andor_records_operators():
    node = parse("mkdir project && cd project").items[0].node

    assert node.operators == ["&&"]
    assert [p.commands[0].argv[0] for p in node.pipelines] == ["mkdir", "cd"]


def test_mixed_andor_chain():
    node = parse("a && b || c").items[0].node
    assert node.operators == ["&&", "||"]


def test_semicolon_makes_separate_items():
    tree = parse("echo one ; echo two")

    assert len(tree.items) == 2
    assert [i.node.pipelines[0].commands[0].argv for i in tree.items] == [
        ["echo", "one"],
        ["echo", "two"],
    ]
    assert [i.background for i in tree.items] == [False, False]


def test_ampersand_marks_background():
    tree = parse("sleep 5 &")

    assert len(tree.items) == 1
    assert tree.items[0].background is True


def test_background_then_another_command():
    tree = parse("sleep 5 & echo done")

    assert [i.background for i in tree.items] == [True, False]


def test_pipeline_binds_tighter_than_andor():
    # `a | b && c` is (a | b) && c, not a | (b && c).
    node = parse("a | b && c").items[0].node

    assert len(node.pipelines) == 2
    assert len(node.pipelines[0].commands) == 2
    assert len(node.pipelines[1].commands) == 1


def test_trailing_separator_is_not_an_empty_command():
    assert len(parse("echo hi ;").items) == 1


def test_empty_line_has_no_items():
    assert parse("").items == []
    assert parse("   ").items == []


def test_dangling_pipe_is_an_error():
    with pytest.raises(ParseError):
        parse("ls |")


def test_redirection_without_target_is_an_error():
    with pytest.raises(ParseError):
        parse("echo hi >")


def test_fd_redirection_is_rejected_by_name():
    # Out of scope for this stage, so say so rather than silently treating the
    # 2 as an argument.
    with pytest.raises(ParseError, match="not supported"):
        parse("ls 2> err.txt")
