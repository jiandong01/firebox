from pydantic import BaseModel
from enum import Enum
from firebox.utils.str import snake_case_to_camel_case


class FileInfo(BaseModel):
    is_dir: bool
    name: str


class FilesystemOperation(str, Enum):
    Create = "Create"
    Write = "Write"
    Remove = "Remove"
    Rename = "Rename"
    Chmod = "Chmod"


class FilesystemEvent(BaseModel):
    path: str
    name: str
    operation: FilesystemOperation
    timestamp: int
    is_dir: bool

    class ConfigDict:
        alias_generator = snake_case_to_camel_case
