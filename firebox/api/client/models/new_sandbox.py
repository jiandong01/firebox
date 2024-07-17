from pydantic import BaseModel, Field
from typing import Optional, Dict


class NewSandbox(BaseModel):
    template_id: str = Field(
        ..., alias="templateID", description="Identifier of the required template"
    )
    metadata: Optional[Dict[str, str]] = Field(
        None, description="Additional metadata for the sandbox"
    )
