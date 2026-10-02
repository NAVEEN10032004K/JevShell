"""What a command is, and what its flags mean.

Classification reads the command's basename, so /bin/rm and rm are the same
thing. Flags are parsed properly rather than matched as one exact spelling,
because `rm -r`, `rm -rf`, `rm -fr` and `rm --recursive` are all recursive.
"""
from enum import Enum
from pathlib import Path


class Category(Enum):
    READ_ONLY = "read_only"
    FILESYSTEM_WRITE = "filesystem_write"
    FILESYSTEM_DELETE = "filesystem_delete"
    PROCESS_CONTROL = "process_control"
    SYSTEM_CONFIGURATION = "system_configuration"
    NETWORK = "network"
    UNKNOWN = "unknown"


CATEGORIES = {
    Category.READ_ONLY: {
        "ls", "pwd", "echo", "cat", "head", "tail", "grep", "find", "wc", "sort",
        "uniq", "diff", "file", "stat", "du", "df", "which", "whoami", "date",
        "env", "printenv", "printf", "basename", "dirname", "realpath", "tree",
        "less", "more", "awk", "sed", "cut", "tr", "md5", "shasum", "man",
    },
    Category.FILESYSTEM_WRITE: {
        "mkdir", "touch", "cp", "ln", "tee", "install", "mktemp", "zip", "tar",
        "unzip", "gzip", "gunzip",
    },
    Category.FILESYSTEM_DELETE: {
        "rm", "rmdir", "mv", "shred", "truncate", "unlink", "dd",
    },
    Category.PROCESS_CONTROL: {
        "kill", "killall", "pkill", "nice", "renice", "trap",
    },
    Category.SYSTEM_CONFIGURATION: {
        "chmod", "chown", "chgrp", "mount", "umount", "sudo", "su", "systemctl",
        "service", "launchctl", "defaults", "dscl", "visudo", "diskutil",
        "mkfs", "fdisk", "sysctl",
    },
    Category.NETWORK: {
        "curl", "wget", "ssh", "scp", "rsync", "ftp", "sftp", "nc", "telnet",
    },
}

NAME_TO_CATEGORY = {
    name: category for category, names in CATEGORIES.items() for name in names
}

# Flags meaning "recurse into directories", across the tools that take one.
RECURSIVE_FLAGS = {"r", "R"}
RECURSIVE_LONG = {"--recursive", "--recurse"}

FORCE_FLAGS = {"f"}
FORCE_LONG = {"--force"}

# Writes that can clobber an existing destination. They are not deletes, so they
# keep their honest category, but they still deserve a confirmation.
OVERWRITING = {"cp", "ln", "install"}


def overwrites(argv: list[str]) -> bool:
    return command_name(argv) in OVERWRITING


def command_name(argv: list[str]) -> str:
    """Basename of argv[0], so an absolute path cannot disguise the command."""
    if not argv:
        return ""

    return Path(argv[0]).name


def classify(argv: list[str]) -> Category:
    """An unrecognized command is UNKNOWN, which policy treats as allowed."""
    return NAME_TO_CATEGORY.get(command_name(argv), Category.UNKNOWN)


def split_options(argv: list[str]) -> tuple[list[str], list[str]]:
    """Separate flags from operands.

    Honours the `--` terminator, so `rm -- -weird-file` treats the filename as an
    operand rather than a flag.
    """
    options: list[str] = []
    operands: list[str] = []
    terminated = False

    for argument in argv[1:]:
        if terminated:
            operands.append(argument)
            continue

        if argument == "--":
            terminated = True
            continue

        if argument.startswith("--"):
            options.append(argument)
        elif argument.startswith("-") and len(argument) > 1:
            options.append(argument)
        else:
            operands.append(argument)

    return options, operands


def short_flags(options: list[str]) -> set[str]:
    """Every clustered short flag, so -rf contributes both r and f."""
    letters = set()

    for option in options:
        if option.startswith("--") or not option.startswith("-"):
            continue
        letters.update(option[1:])

    return letters


def is_recursive(argv: list[str]) -> bool:
    options, _ = split_options(argv)

    if short_flags(options) & RECURSIVE_FLAGS:
        return True

    return any(option in RECURSIVE_LONG for option in options)


def is_forced(argv: list[str]) -> bool:
    options, _ = split_options(argv)

    if short_flags(options) & FORCE_FLAGS:
        return True

    return any(option in FORCE_LONG for option in options)


def path_operands(argv: list[str]) -> list[str]:
    """Operands, which for these commands are the paths being acted on."""
    _, operands = split_options(argv)

    return operands
