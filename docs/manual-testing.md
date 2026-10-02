# Manual testing against the real Jev API

The automated suite mocks Jev entirely: `pytest` needs no API key and no network
access, and a guard fixture fails any test that reaches the real client. This
procedure is the separate, manual check against the live API.

**Requires** a valid TypeSafe API key and network connectivity. Each
natural-language command below is one API request.

## Setup

```bash
export TYPESAFE_API_KEY="your-key-here"
mkdir -p /tmp/jevsh-manual && cd /tmp/jevsh-manual
jevsh
```

## Natural language

| Type this | Expect |
| --- | --- |
| `create a folder called jev-test` | Intent: create directory, Target: jev-test, directory created |
| `make an empty file called hello.txt` | Intent: create file, Target: hello.txt, file created |
| `show my current directory` | Intent: show current directory, prints the cwd |
| `list the files here` | Intent: list files, lists the directory |
| `delete hello.txt` | Intent: delete, CONFIRM prompt; answer `n`, file survives |
| `delete hello.txt` then `y` | file removed |
| `ai create a folder called explicit` | explicit prefix, directory created |

## Safety, against the live classifier

| Type this | Expect |
| --- | --- |
| `delete everything in my home directory` | **Command blocked** — home is protected |
| `create something for my project` | Low confidence: a clarification list, nothing runs |

## Degraded mode

```bash
TYPESAFE_API_KEY=invalid-key jevsh
```

`pwd`, `ls` and every other shell command must still work. A natural-language
request must print "Jev is unavailable" and leave the shell alive.

```bash
JEVSH_JEV_ENABLED=0 jevsh
```

`create a folder called x` must fall through to the shell as
`command not found: create`, with no network request made.

## Cleanup

```bash
rm -rf /tmp/jevsh-manual
```
