from pydantic import BaseModel, Field
from typing import Optional


class FileSystemOperation(BaseModel):
    operation: str = Field(..., description="Type of filesystem operation")
    path: str = Field(..., description="Path for the filesystem operation")
    content: Optional[str] = Field(
        default=None, description="Content for write operations"
    )
    timeout: int = Field(
        default=30, description="Timeout for the filesystem operation in seconds"
    )
