from pydantic import BaseModel


class TerminalOutput(BaseModel):
    data: str = ""

    def _add_data(self, data: str) -> None:
        self.data += data
