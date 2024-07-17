import asyncio
from firebox.logging import logger
from typing import Callable, List


class CleanupManager:
    def __init__(self):
        self.cleanup_tasks: List[Callable] = []

    def add_task(self, task: Callable):
        self.cleanup_tasks.append(task)

    async def cleanup(self):
        for task in reversed(self.cleanup_tasks):
            try:
                if asyncio.iscoroutinefunction(task):
                    await task()
                else:
                    task()
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")


cleanup_manager = CleanupManager()
