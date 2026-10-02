"""The repository ships as an installable, secret-free package."""
import tomllib
from pathlib import Path

import jevsh

ROOT = Path(__file__).resolve().parent.parent


def pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text())


def test_project_metadata_is_complete():
    project = pyproject()["project"]

    assert project["name"] == "jevsh"
    assert project["description"]
    assert project["requires-python"]
    assert project["readme"] == "README.md"


def test_the_console_script_points_at_a_real_callable():
    target = pyproject()["project"]["scripts"]["jevsh"]

    assert target == "jevsh.cli:main"

    from jevsh.cli import main

    assert callable(main)


def test_runtime_dependencies_are_only_what_is_imported():
    # The old requirements.txt pinned certifi, idna, charset-normalizer and
    # urllib3 -- all transitive dependencies of requests, not direct ones.
    dependencies = pyproject()["project"]["dependencies"]

    assert len(dependencies) == 1
    assert dependencies[0].startswith("requests")


def test_pytest_is_a_development_extra_not_a_runtime_dependency():
    project = pyproject()["project"]

    assert any("pytest" in d for d in project["optional-dependencies"]["dev"])
    assert not any("pytest" in d for d in project["dependencies"])


def test_the_version_is_declared_once():
    project = pyproject()["project"]

    assert project["dynamic"] == ["version"]
    assert jevsh.__version__


def test_gitignore_covers_secrets_and_artifacts():
    ignored = (ROOT / ".gitignore").read_text()

    for pattern in (".env", "venv/", "__pycache__/", ".pytest_cache", "*.egg-info/", "dist/"):
        assert pattern in ignored, pattern


def tracked_files():
    """Everything that would be committed: source, tests, docs, config."""
    for pattern in ("src/**/*.py", "tests/**/*.py", "*.md", "docs/*.md",
                    "*.toml", "*.txt", ".gitignore", ".env.example"):
        yield from ROOT.glob(pattern)


def test_the_real_api_key_is_not_in_any_tracked_file():
    """The developer's actual credential must not appear outside .env.

    This asks the precise question rather than pattern-matching: it reads the
    real key, if one is configured locally, and checks it is nowhere a commit
    would reach. The key itself is never printed, even on failure.
    """
    env_file = ROOT / ".env"

    if not env_file.is_file():
        pytest.skip("no local .env to check against")

    secrets = set()

    for line in env_file.read_text().splitlines():
        _, separator, value = line.partition("=")
        value = value.strip().strip("\"'")

        if separator and len(value) >= 12:
            secrets.add(value)

    if not secrets:
        pytest.skip(".env holds no value long enough to be a credential")

    for path in tracked_files():
        text = path.read_text(errors="ignore")

        for secret in secrets:
            assert secret not in text, f"credential found in {path.relative_to(ROOT)}"


def test_env_is_ignored_so_the_key_cannot_be_committed():
    assert ".env" in (ROOT / ".gitignore").read_text()


def test_the_key_is_never_interpolated_into_a_message():
    """The key reaches exactly one place: the Authorization header."""
    import ast as python_ast

    client = (ROOT / "src" / "jevsh" / "jev.py").read_text()
    uses = [
        line for line in client.splitlines()
        if "api_key()" in line and not line.lstrip().startswith("def ")
    ]

    # One call site, and it is the header.
    assert len(uses) == 1, uses
    assert "Authorization" in uses[0]

    # And api_key() is never an argument to print or to a logging call. Matched
    # by exact function name, so the boolean has_api_key() is not confused for
    # the credential itself.
    def returns_the_key(node):
        return (
            isinstance(node, python_ast.Call)
            and isinstance(node.func, python_ast.Name)
            and node.func.id == "api_key"
        )

    for path in (ROOT / "src").rglob("*.py"):
        for node in python_ast.walk(python_ast.parse(path.read_text())):
            if not isinstance(node, python_ast.Call):
                continue

            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)

            if name not in {"print", "debug", "info", "warning", "error", "exception"}:
                continue

            for argument in python_ast.walk(node):
                assert not returns_the_key(argument), f"{path}:{node.lineno}"


def test_the_example_env_file_holds_no_value():
    example = (ROOT / ".env.example").read_text()

    assert "TYPESAFE_API_KEY" in example
    assert 'TYPESAFE_API_KEY=""' in example


def test_readme_documents_the_essentials():
    readme = (ROOT / "README.md").read_text()

    for section in ("## Installation", "## Configuration", "## Usage",
                    "## Architecture", "## Limitations", "## Development"):
        assert section in readme, section

    # The safety contract must be stated, not implied.
    assert "never execute" in readme.lower() or "never executes" in readme.lower()


def test_readme_contains_no_real_key():
    readme = (ROOT / "README.md").read_text()

    assert "your-key-here" in readme
    assert "sk-" not in readme
