"""The policy layer sees every command, however it is wrapped."""
from pathlib import Path

from jevsh.shell.parser import parse
from jevsh.shell.policy import check, describe
from jevsh.shell.repl import dispatch


def effects_for(line, session):
    tree = parse(line, env=session.environment, cwd=session.cwd, aliases=session.aliases)
    return describe(tree, session)


def test_effects_record_argv(session):
    effects = effects_for("ls -la", session)

    assert len(effects) == 1
    assert effects[0].argv == ["ls", "-la"]
    assert effects[0].destructive is False


def test_effects_record_write_targets(session, tmp_path):
    effects = effects_for("echo hi > out.txt", session)

    assert effects[0].writes == [str(tmp_path / "out.txt")]
    assert effects[0].reads == []


def test_effects_record_append_as_a_write(session, tmp_path):
    assert effects_for("echo hi >> out.txt", session)[0].writes == [
        str(tmp_path / "out.txt")
    ]


def test_effects_record_read_targets(session, tmp_path):
    effects = effects_for("cat < in.txt", session)

    assert effects[0].reads == [str(tmp_path / "in.txt")]
    assert effects[0].writes == []


def test_rm_is_classified_destructive(session):
    assert effects_for("rm notes.txt", session)[0].destructive is True


def test_redirection_does_not_launder_rm(session):
    # The §16 case: rm must stay destructive even wrapped in a redirect.
    effects = effects_for("rm important.txt > output.txt", session)

    assert len(effects) == 1
    assert effects[0].destructive is True
    assert effects[0].argv == ["rm", "important.txt"]


def test_a_pipe_does_not_launder_rm(session):
    effects = effects_for("rm important.txt | cat", session)

    assert len(effects) == 2
    assert effects[0].destructive is True
    assert effects[1].destructive is False


def test_every_operator_still_exposes_the_command(session):
    for line in (
        "rm x && echo done",
        "rm x || echo done",
        "echo done ; rm x",
        "rm x | cat",
        "rm x > log",
        "rm x &",
    ):
        effects = effects_for(line, session)
        assert any(e.destructive for e in effects), line


def test_commands_in_a_long_chain_are_all_seen(session):
    effects = effects_for("a | b && c || d ; e", session)

    assert [e.name for e in effects] == ["a", "b", "c", "d", "e"]


def test_ordinary_destructive_work_is_allowed(session, tmp_path):
    (tmp_path / "notes.txt").write_text("x")

    assert check(effects_for("rm notes.txt", session), session) is None


def test_deleting_home_is_blocked(session):
    refusal = check(effects_for(f"rm -rf {Path.home()}", session), session)

    assert refusal is not None
    assert "refusing to delete" in refusal


def test_deleting_root_is_blocked(session):
    assert check(effects_for("rm -rf /", session), session) is not None


def test_writing_to_home_is_blocked(session):
    refusal = check(effects_for(f"echo x > {Path.home()}", session), session)

    assert refusal is not None
    assert "refusing to write" in refusal


def test_options_are_not_mistaken_for_paths(session, tmp_path):
    # "-rf" must not be resolved as a filename.
    (tmp_path / "doomed").mkdir()

    assert check(effects_for("rm -rf doomed", session), session) is None


def test_block_happens_before_execution(session, capfd):
    from jevsh.shell.executor import BLOCKED

    status = dispatch(f"rm -rf {Path.home()}", session)

    # A refusal has its own exit code, so a script can tell it from a command
    # that merely failed.
    assert status == BLOCKED
    assert "blocked" in capfd.readouterr().out
    assert Path.home().exists()


def test_a_blocked_command_blocks_the_whole_line(session, tmp_path, capfd):
    # Policy runs on the tree, so a safe command sharing the line is not run.
    dispatch(f"echo safe > marker.txt ; rm -rf {Path.home()}", session)

    assert not (tmp_path / "marker.txt").exists()
    assert "blocked" in capfd.readouterr().out


def test_alias_cannot_smuggle_a_destructive_command(session, capfd):
    # Aliases expand at parse time precisely so this cannot slip past.
    dispatch('alias wipe="rm -rf"', session)
    capfd.readouterr()

    from jevsh.shell.executor import BLOCKED

    status = dispatch(f"wipe {Path.home()}", session)

    assert status == BLOCKED
    assert "blocked" in capfd.readouterr().out
    assert Path.home().exists()


def test_one_engine_serves_typed_and_natural_language(session):
    """A Jev intent and a typed command reach the same verdict.

    There is a single entry point now: natural language is converted to a
    SimpleCommand before it is judged, so there is no second code path to keep
    in step.
    """
    from jevsh.jev_intent import JevIntent, to_command
    from jevsh.models import ActionType
    from jevsh.safety import evaluate
    from jevsh.shell.ast import AndOr, Pipeline, Sequence, SequenceItem
    from jevsh.shell.parser import parse

    from_jev = to_command(JevIntent(ActionType.DELETE, 1.0, str(Path.home())), session)
    jev_tree = Sequence([SequenceItem(AndOr([Pipeline([from_jev])], []))])
    typed_tree = parse(f"rm -r {Path.home()}", env=session.environment, cwd=session.cwd)

    assert evaluate(jev_tree, session).level is evaluate(typed_tree, session).level
