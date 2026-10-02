# JevShell

A Unix shell for macOS and Linux with two things most shells do not have: a
**deterministic safety policy** that grades every command before it runs, and
**optional natural-language commands** powered by [TypeSafe Jev](https://typesafe.ai).

```
jevsh ~/projects> create a folder called reports

Jev:
  Intent: create directory
  Target: reports

jevsh ~/projects> rm -rf /
Command blocked:
    Refusing to delete the filesystem root.
```

The AI never executes anything. Jev classifies a request into one of five
operations; deterministic code turns that into an ordinary command, and the same
safety engine that guards your typed commands guards that one too.

## Architecture

```
            input line
                 |
         +-------v--------+
         |  input router  |   deterministic, offline
         +---+--------+---+
             |        |
       shell |        | natural language
             |        v
             |      Jev  ->  structured intent  ->  deterministic extraction
             |        |
             v        v
            command AST / IR
                 |
         +-------v--------+
         | safety policy  |   deterministic, never calls Jev
         +---+-----+----+-+
             |     |    |
          ALLOW CONFIRM BLOCK
             |     |      X
             |   ask the user
             |     |
         +---v-----v---+
         |  executor   |   subprocess.Popen, never shell=True
         +-------------+
```

Two rules hold everywhere:

1. **Jev never executes commands.** Its answer is one of five enum members.
   Anything else is rejected, so no model output can become a command.
2. **Nothing reaches the executor without passing safety**, whether it was typed,
   aliased, piped, chained, backgrounded, redirected or produced by Jev.

## Installation

```bash
git clone <repository-url>
cd jevsh
python3 -m venv venv
source venv/bin/activate
pip install .
```

Requires Python 3.10 or newer. The only runtime dependency is `requests`.

Then run:

```bash
jevsh              # interactive
jevsh --help
jevsh --version
```

For development, install the test extra and run the suite:

```bash
pip install -e '.[dev]'
pytest
```

The suite needs no API key and no network access.

## Configuration

Natural-language commands need a TypeSafe API key:

```bash
export TYPESAFE_API_KEY="your-key-here"
```

Without it the shell works normally; only natural language is unavailable, and
it says so. Never commit a real key — `.gitignore` already excludes `.env`.

| Variable | Effect |
| --- | --- |
| `TYPESAFE_API_KEY` | Enables natural-language commands |
| `JEVSH_JEV_ENABLED=0` | Disables Jev entirely; everything runs as a shell command |
| `JEVSH_LOG_LEVEL=DEBUG` | Diagnostics on stderr. Never logs keys, headers or payloads |
| `NO_COLOR` / `JEVSH_NO_COLOR` | Disables colored output |

## Usage

### Ordinary shell commands

These never touch the network:

```
jevsh ~/code> pwd
jevsh ~/code> ls -lah
jevsh ~/code> cd project
jevsh ~/code/project> git status
jevsh ~/code/project> python --version
```

### Natural language

A line that is not a recognisable command is sent to Jev:

```
jevsh ~/code> create a folder called projects
jevsh ~/code> make an empty file called notes.txt
jevsh ~/code> show my current directory
jevsh ~/code> list the files here
jevsh ~/code> delete notes.txt
```

To be explicit, prefix with `ai`:

```
jevsh ~/code> ai create a folder called projects
```

Routing is deterministic: a word that is a builtin, an alias or on your `PATH` is
treated as a command, and anything containing a shell operator is shell. Only
unrecognised input reaches Jev, so a typed command never costs a round trip.

### Safety

Every command is graded **ALLOW**, **CONFIRM** or **BLOCK**.

```
jevsh ~/code> rm important.txt

This command requires confirmation:
    rm important.txt

Reason:
    Deletes or moves files.

Continue? [y/N]:
```

Only an explicit `y` proceeds; empty input cancels.

```
jevsh ~/code> rm -rf ~
Command blocked:
    Refusing to delete /Users/you.
```

A BLOCK is never offered a prompt. There is no answer that makes it run.

The policy reads the whole command tree, so none of these get through:

```
rm -rf / ; echo safe          blocked
echo data | rm -rf ~          blocked
alias destroy="rm -rf"        destroy /   -> blocked
RM=rm                         $RM -rf /   -> blocked
/bin/rm -rf /                 blocked
rm -rf .                      blocked when the current directory is home
```

Non-interactive callers never hang: a CONFIRM is reported and skipped.

```bash
jevsh -c "rm notes.txt"               # reports CONFIRM, runs nothing
jevsh --dry-run -c "rm -rf /"         # shows the decision, runs nothing
```

Exit codes: `0` success, `1` the command failed, `2` invalid input,
`77` refused by policy, `126` not executable, `127` not found, `130` interrupted.

## Supported shell features

| Area | Supported |
| --- | --- |
| Builtins | `cd` (`-`, `~`, `..`), `pwd`, `history [n]`, `clear`, `alias`, `unalias`, `export`, `unset`, `jobs`, `exit [n]`, `quit` |
| Pipelines | `a \| b \| c`, arbitrary length, exit status from the last stage |
| Redirection | `>`, `>>`, `<` |
| Chaining | `;`, `&&`, `\|\|` with short-circuit semantics |
| Background | `cmd &` with `jobs` |
| Expansion | `$VAR`, `${VAR}`, `~`, globs `*` `?` `[]` |
| Quoting | single quotes literal, double quotes expand, backslash escapes |
| Signals | Ctrl+C interrupts the command, Ctrl+D exits cleanly |

## Limitations

Honest list of what is **not** implemented:

- No command substitution (`$(...)`, backticks) — these stay literal text and
  are never executed.
- No subshells or grouping, heredocs, brace expansion, or arithmetic expansion.
- No `2>`, `2>&1`, or other file-descriptor redirection.
- No `fg`, `bg`, Ctrl+Z, or terminal job control. Background jobs are tracked but
  cannot be resumed in the foreground.
- No tab completion and no persistent history; history is per session.
- No field splitting after expansion: `X="a b"; cmd $X` passes one argument.
- A builtin inside a pipeline falls back to the external binary, so `pwd | cat`
  works but `history | grep` is not found.
- Natural language covers five operations only: create directory, create file,
  list, show directory, delete. It cannot express pipelines or redirection.
- Jev's confidence measures how clearly the options separated, not whether the
  request made sense. Safety, not confidence, is what protects you.
- **Safety is a guard rail, not a sandbox.** Paths are checked before execution,
  so a path that changes in between (TOCTOU) defeats the check. Policy reads
  argv, so it cannot see what `python script.py` or `make install` will do.

## Development

```
src/jevsh/
    cli.py              argument parsing, one-shot and dry-run entry points
    __main__.py         python -m jevsh
    config.py           environment-driven settings
    ui.py               user-facing formatting and color

    jev.py              TypeSafe HTTP client (the only networking code)
    jev_router.py       shell vs natural-language routing
    jev_intent.py       structured intent, and intent -> command conversion
    extractor.py        deterministic target extraction
    models.py           ActionType, the bounded intent vocabulary

    shell/
        repl.py         interactive loop, prompt, signal handling
        session.py      cwd, environment, history, aliases, jobs
        parser.py       tokenizer (quote-aware) and grammar
        ast.py          SimpleCommand, Pipeline, AndOr, Sequence
        executor.py     process execution
        builtins.py     builtin dispatch table
        aliases.py      alias expansion with cycle detection
        environment.py  variable expansion, export/unset
        jobs.py         background job table
        policy.py       thin shell-facing view of the safety engine

    safety/
        policy.py       evaluate() -- the single entry point
        filesystem.py   path canonicalization and protected locations
        commands.py     command categories and flag parsing
        result.py       SafetyLevel, SafetyResult
```

**The rule to preserve:** Jev never executes commands. Every action goes
AST → Safety → Executor. If you add a feature, add it to the AST and let the
existing safety engine see it; do not add a second execution path.

Manual testing against the real API is documented in
[`docs/manual-testing.md`](docs/manual-testing.md) and is deliberately outside
the automated suite.

## License

MIT.
