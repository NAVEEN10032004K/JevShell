import os
from pathlib import Path

import requests

# Short enough that a hung API cannot make the shell look frozen. No retries:
# an interactive user can simply press enter again.
TIMEOUT_SECONDS = 10

API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"


class JevError(Exception):
    pass


def _load_env_file():
    """Read KEY = "value" pairs from a .env beside the project, if present."""
    for parent in Path(__file__).resolve().parents:
        env_file = parent / ".env"

        if not env_file.is_file():
            continue

        for line in env_file.read_text().splitlines():
            key, _, value = line.partition("=")

            if _ and key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip().strip("\"'")

        return


def api_key() -> str:
    key = os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API")

    if not key:
        _load_env_file()
        key = os.getenv("TYPESAFE_API_KEY") or os.getenv("JEV_API")

    if not key:
        raise JevError(
            "No API key found. Set TYPESAFE_API_KEY (or JEV_API) in the "
            "environment or in a .env file."
        )

    return key


def ask_jev(state: str):

    payload = {
        "model": MODEL,
        "state": state,
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": "Determine which filesystem operation the user wants.",
                "criteria": {
                    "mkdir": "Create a new directory or folder.",
                    "touch": "Create a new empty file.",
                    "ls": "List files and directories.",
                    "pwd": "Show the current working directory.",
                    "delete": "Delete a file or directory."
                }
            }
        }
    }

    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )

    if not response.ok:
        raise JevError(
            f"Jev API error {response.status_code}: "
            f"{response.text}"
        )

    return response.json()