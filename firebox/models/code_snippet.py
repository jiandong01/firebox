from pydantic import BaseModel


class OpenPort(BaseModel):
    ip: str
    port: int
    state: str


class CodeSnippet(BaseModel):
    name: str
    content: str
