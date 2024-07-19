import asyncio
import websockets
import json
from typing import Dict, Any


class WebSocketServer:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.clients = set()

    async def handler(self, websocket, path):
        self.clients.add(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        finally:
            self.clients.remove(websocket)

    async def handle_message(self, websocket, message):
        data = json.loads(message)
        method = data.get("method")
        params = data.get("params", [])

        if method == "execute":
            result = await self.sandbox.communicate(*params)
            await websocket.send(json.dumps({"result": result}))
        elif method == "start_terminal":
            terminal = await self.sandbox.terminal.start(*params)
            await websocket.send(
                json.dumps({"result": {"terminal_id": terminal.terminal_id}})
            )
        elif method == "terminal_input":
            terminal_id, input_data = params
            terminal = await self.sandbox.terminal.get(terminal_id)
            if terminal:
                await terminal.send_data(input_data)
        elif method == "add_script":
            name, content = params
            await self.sandbox.add_script(name, content)
            await websocket.send(json.dumps({"result": "Script added successfully"}))
        # Add more methods as needed

    async def broadcast(self, message: Dict[str, Any]):
        if self.clients:
            await asyncio.wait(
                [client.send(json.dumps(message)) for client in self.clients]
            )

    def start(self, host: str = "localhost", port: int = 8765):
        server = websockets.serve(self.handler, host, port)
        asyncio.get_event_loop().run_until_complete(server)
        asyncio.get_event_loop().run_forever()
