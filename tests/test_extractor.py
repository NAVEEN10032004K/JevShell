"""Deterministic target extraction.

The extractor is what turns a natural-language request into a path. Jev picks
the operation; this picks the target, and only ever from words the user typed.
"""
from pathlib import Path

from jevsh.extractor import extract_path


def test_finds_targets_in_ordinary_phrasings():
    assert extract_path("make a folder called reports") == "reports"
    assert extract_path("create a directory named projects") == "projects"
    assert extract_path("make a file called notes.txt") == "notes.txt"
    assert extract_path("delete the file notes.txt") == "notes.txt"
    assert extract_path("list files in /tmp") == "/tmp"


def test_rejects_filler_nouns():
    # Without this, "list files" would try to list a directory named "files".
    assert extract_path("list files") is None
    assert extract_path("delete the file") is None
    assert extract_path("delete it") is None
    assert extract_path("remove everything") is None


def test_resolves_home_so_safety_can_block_it():
    assert extract_path("delete everything in my home folder") == str(Path.home())
    assert extract_path("delete everything in my home directory") == str(Path.home())


def test_a_target_is_always_a_word_the_user_typed():
    request = "delete the old project"

    assert extract_path(request) in request


def test_no_target_is_reported_rather_than_invented():
    for request in ("delete", "please help", "do something"):
        assert extract_path(request) is None, request
