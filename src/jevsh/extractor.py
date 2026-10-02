import re
from pathlib import Path


# Words the patterns below can capture when the sentence names no path at all
# ("list files"). None of them is ever a real target.
NOT_A_PATH = {
    "file", "files", "folder", "folders", "directory", "directories",
    "everything", "all", "it", "this", "that", "them", "stuff", "contents",
}


def extract_path(user_input: str) -> str | None:
    text = user_input.strip()

    # Handle dangerous "everything/all in home" FIRST.
    if re.search(
        r"(?:delete|remove).*(?:everything|all).*(?:home directory|home folder|home)",
        text,
        re.IGNORECASE,
    ):
        return str(Path.home())

    patterns = [
        # Create folder/directory
        r"(?:folder|directory)\s+(?:called|named)\s+([^\s]+)",

        # Create file
        r"(?:file)\s+(?:called|named)\s+([^\s]+)",

        # Delete a specific file/folder
        r"(?:delete|remove)\s+(?:the\s+)?(?:file|folder|directory)?\s*([^\s]+)",

        # List a directory
        r"(?:list|show)\s+(?:the\s+)?(?:files\s+in\s+)?([^\s]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match and match.group(1).lower().strip(".,!?") not in NOT_A_PATH:
            return match.group(1)

    return None