"""Entry point for `python -m jevsh`, alongside the installed `jevsh` script."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main() or 0)
