from pydantic import BaseModel, Field
from typing import Optional


class Sandbox(BaseModel):
    template_id: str = Field(
        ..., alias="templateID", description="Identifier of the template"
    )
    sandbox_id: str = Field(
        ..., alias="sandboxID", description="Identifier of the sandbox"
    )
    client_id: str = Field(
        ..., alias="clientID", description="Identifier of the client"
    )
    alias: Optional[str] = Field(None, description="Alias of the template")
