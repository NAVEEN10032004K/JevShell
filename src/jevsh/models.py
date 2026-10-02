from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ActionType(Enum):
    MKDIR = "mkdir"
    TOUCH = "touch"
    LS = "ls"
    PWD = "pwd"
    DELETE = "delete"


@dataclass
class Action:
    type: ActionType
    path: Optional[str] = None
    confidence: float = 1.0