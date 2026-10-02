"""Environment-driven settings, and that none of them hold secrets."""
import logging

from jevsh import config, ui


def test_color_is_off_when_not_a_terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("JEVSH_NO_COLOR", raising=False)

    # pytest captures stdout, so this is the ordinary piped case.
    assert config.color_enabled() is False
    assert ui.paint("hello", "red") == "hello"


def test_no_color_is_honoured_however_it_is_set(monkeypatch):
    class Terminal:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setenv("NO_COLOR", "")
    assert config.color_enabled(Terminal()) is False

    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("JEVSH_NO_COLOR", "1")
    assert config.color_enabled(Terminal()) is False

    monkeypatch.delenv("JEVSH_NO_COLOR")
    assert config.color_enabled(Terminal()) is True


def test_painted_output_carries_no_escape_codes_when_disabled(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")

    for text in (ui.blocked("nope"), ui.error("bad"), ui.paint("x", "green")):
        assert "\033" not in text


def test_jev_can_be_disabled(monkeypatch):
    monkeypatch.delenv("JEVSH_JEV_ENABLED", raising=False)
    assert config.jev_enabled() is True

    for off in ("0", "false", "no", "off", "FALSE"):
        monkeypatch.setenv("JEVSH_JEV_ENABLED", off)
        assert config.jev_enabled() is False, off

    monkeypatch.setenv("JEVSH_JEV_ENABLED", "1")
    assert config.jev_enabled() is True


def test_logging_is_quiet_by_default(monkeypatch):
    monkeypatch.delenv("JEVSH_LOG_LEVEL", raising=False)
    config.configure_logging()

    assert logging.getLogger().level >= logging.WARNING


def test_logging_level_can_be_raised(monkeypatch):
    monkeypatch.setenv("JEVSH_LOG_LEVEL", "DEBUG")
    config.configure_logging()

    assert logging.getLogger().level == logging.DEBUG

    # Leave the root logger as the rest of the suite expects it.
    logging.getLogger().setLevel(logging.WARNING)


def test_an_invalid_level_falls_back_quietly(monkeypatch):
    monkeypatch.setenv("JEVSH_LOG_LEVEL", "LOUD")
    config.configure_logging()

    assert logging.getLogger().level >= logging.WARNING


def test_config_never_holds_the_api_key(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "sk-should-not-be-copied")

    # The key is read where it is used, not cached in a settings object that
    # could end up in a log line or a repr.
    source = (config.__file__)
    text = open(source).read()

    assert "TYPESAFE_API_KEY" not in text.replace("# ", "")
