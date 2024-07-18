import os
import base64
from typing import List, Union
from .logs import logger
from .watcher import Watcher


class Filesystem:
    def __init__(self, sandbox):
        self.sandbox = sandbox

    def _get_full_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(self.sandbox.cwd, path)

    async def upload_file(self, local_path: str, remote_path: str):
        logger.info(f"Uploading file from {local_path} to {remote_path}")

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file does not exist: {local_path}")

        full_remote_path = self._get_full_path(remote_path)

        # Create the directory structure if it doesn't exist
        remote_dir = os.path.dirname(full_remote_path)
        await self.sandbox.communicate(f"mkdir -p {remote_dir}")

        with open(local_path, "rb") as local_file:
            content = local_file.read()

        encoded_content = base64.b64encode(content).decode()

        result, exit_code = await self.sandbox.communicate(
            f"echo '{encoded_content}' | base64 -d > {full_remote_path}"
        )

        if exit_code != 0:
            raise IOError(f"Failed to upload file: {result}")

        logger.info("Upload completed successfully")
        return full_remote_path

    async def download_file(self, remote_path: str, local_path: str):
        logger.info(f"Downloading file from {remote_path} to {local_path}")

        full_remote_path = self._get_full_path(remote_path)

        # Check if the remote file exists
        exists_result, exists_exit_code = await self.sandbox.communicate(
            f"[ -f {full_remote_path} ]"
        )
        if exists_exit_code != 0:
            raise FileNotFoundError(f"Remote file does not exist: {full_remote_path}")

        result, exit_code = await self.sandbox.communicate(f"base64 {full_remote_path}")

        if exit_code != 0:
            raise IOError(f"Failed to download file: {result}")

        try:
            decoded_content = base64.b64decode(result)
        except:
            raise IOError("Failed to decode base64 content")

        with open(local_path, "wb") as local_file:
            local_file.write(decoded_content)

        logger.info("Download completed successfully")
        return local_path

    async def list(self, path: str) -> List[str]:
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(f"ls -1a {full_path}")
        if exit_code != 0:
            raise FileNotFoundError(
                f"Directory not found or couldn't be listed: {full_path}"
            )
        return [
            item for item in result.splitlines() if item and item not in [".", ".."]
        ]

    async def read(self, path: str) -> bytes:
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(f"cat {full_path}")
        if exit_code != 0:
            raise FileNotFoundError(f"File not found or couldn't be read: {full_path}")
        return result.encode("utf-8")

    async def write(self, path: str, content: Union[str, bytes]):
        full_path = self._get_full_path(path)
        if isinstance(content, str):
            content = content.encode("utf-8")

        # Create the directory if it doesn't exist
        dir_path = os.path.dirname(full_path)
        await self.sandbox.communicate(f"mkdir -p {dir_path}")

        # Write content to file
        encoded_content = content.replace(b"'", b"'\"'\"'")  # Escape single quotes
        command = f"echo -n '{encoded_content.decode()}' > {full_path}"
        result, exit_code = await self.sandbox.communicate(command)

        if exit_code != 0:
            raise IOError(f"Failed to write to file: {full_path}")

        return full_path

    async def delete(self, path: str):
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(
            f"rm -rf '{full_path}' && echo 'deleted' || echo 'failed'"
        )
        if exit_code != 0 or "failed" in result:
            raise FileNotFoundError(
                f"File or directory not found or couldn't be deleted: {full_path}"
            )

    async def make_dir(self, path: str):
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(f"mkdir -p {full_path}")
        if exit_code != 0:
            raise OSError(f"Couldn't create directory: {full_path}")

    async def exists(self, path: str) -> bool:
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(
            f"[ -e {full_path} ] && echo 'exists' || echo 'not exists'"
        )
        return exit_code == 0 and "exists" == result

    async def is_file(self, path: str) -> bool:
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(
            f"[ -f {full_path} ] && echo 'is file' || echo 'not file'"
        )
        return exit_code == 0 and "is file" == result

    async def is_dir(self, path: str) -> bool:
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(
            f"[ -d {full_path} ] && echo 'is dir' || echo 'not dir'"
        )
        return exit_code == 0 and "is dir" == result

    async def get_size(self, path: str) -> int:
        full_path = self._get_full_path(path)
        result, exit_code = await self.sandbox.communicate(
            f"du -sb {full_path} | cut -f1"
        )
        if exit_code != 0:
            raise OSError(f"Couldn't get size of: {full_path}")
        try:
            return int(result.strip())
        except ValueError:
            raise OSError(f"Unexpected output when getting size of: {full_path}")

    def watch_dir(self, path: str) -> Watcher:
        full_path = self._get_full_path(path)
        return Watcher(self, full_path)
