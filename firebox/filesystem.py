import os
import asyncio
from typing import List, Union, Callable
import base64
from .config import config
from .logs import logger
from .watcher import Watcher


class Filesystem:
    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.persistent_root = getattr(config, "persistent_storage_path", "/home/user")

    async def upload_file(self, local_path: str, remote_path: str):
        logger.info(f"Uploading file from {local_path} to {remote_path}")

        if not os.path.exists(local_path):
            logger.error(f"Local file does not exist: {local_path}")
            raise FileNotFoundError(f"Local file does not exist: {local_path}")

        full_remote_path = os.path.join(self.persistent_root, remote_path.lstrip("/"))
        logger.debug(f"Full remote path: {full_remote_path}")

        # Create the directory structure if it doesn't exist
        remote_dir = os.path.dirname(full_remote_path)
        mkdir_result, mkdir_exit_code = await self.sandbox.communicate(
            f"mkdir -p {remote_dir}"
        )
        logger.debug(f"mkdir command exit code: {mkdir_exit_code}")
        logger.debug(f"mkdir command result: {mkdir_result}")

        if mkdir_exit_code != 0:
            logger.error(f"Failed to create directory structure: {mkdir_result}")
            raise IOError(f"Failed to create directory structure: {mkdir_result}")

        with open(local_path, "rb") as local_file:
            content = local_file.read()
            logger.debug(f"Read {len(content)} bytes from local file")

        encoded_content = base64.b64encode(content).decode()

        result, exit_code = await self.sandbox.communicate(
            f"echo '{encoded_content}' | base64 -d > {full_remote_path}"
        )
        logger.debug(f"Upload command exit code: {exit_code}")
        logger.debug(f"Upload command result: {result}")

        if exit_code != 0:
            logger.error(f"Upload failed with exit code {exit_code}: {result}")
            raise IOError(f"Failed to upload file: {result}")

        logger.info("Upload completed successfully")
        return full_remote_path, exit_code

    async def download_file(self, remote_path: str, local_path: str):
        logger.info(f"Downloading file from {remote_path} to {local_path}")

        full_remote_path = os.path.join(self.persistent_root, remote_path.lstrip("/"))
        logger.debug(f"Full remote path: {full_remote_path}")

        # Check if the remote file exists
        exists_result, exists_exit_code = await self.sandbox.communicate(
            f"[ -f {full_remote_path} ]"
        )
        if exists_exit_code != 0:
            logger.error(f"Remote file does not exist: {full_remote_path}")
            raise FileNotFoundError(f"Remote file does not exist: {full_remote_path}")

        result, exit_code = await self.sandbox.communicate(f"base64 {full_remote_path}")
        logger.debug(f"Download command exit code: {exit_code}")
        logger.debug(f"Downloaded content length: {len(result)}")

        if exit_code != 0:
            logger.error(f"Download failed with exit code {exit_code}: {result}")
            raise IOError(f"Failed to download file: {result}")

        try:
            decoded_content = base64.b64decode(result)
        except:
            logger.error("Failed to decode base64 content")
            raise IOError("Failed to decode base64 content")

        with open(local_path, "wb") as local_file:
            local_file.write(decoded_content)
        logger.debug(f"Wrote {len(decoded_content)} bytes to local file")

        logger.info("Download completed successfully")
        return local_path, exit_code

    async def list(self, path: str) -> List[str]:
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
        result, exit_code = await self.sandbox.communicate(f"ls -1a {full_path}")
        if exit_code != 0:
            raise FileNotFoundError(
                f"Directory not found or couldn't be listed: {full_path}"
            )
        return [
            item for item in result.splitlines() if item and item not in [".", ".."]
        ]

    async def read(self, path: str) -> bytes:
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
        result, exit_code = await self.sandbox.communicate(f"cat {full_path}")
        if exit_code != 0:
            raise FileNotFoundError(f"File not found or couldn't be read: {full_path}")
        return result.encode("utf-8")

    async def delete(self, path: str):
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
        result, exit_code = await self.sandbox.communicate(
            f"rm -rf '{full_path}' && echo 'deleted' || echo 'failed'"
        )
        if exit_code != 0 or "failed" in result:
            raise FileNotFoundError(
                f"File or directory not found or couldn't be deleted: {full_path}"
            )

    async def make_dir(self, path: str):
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
        result, exit_code = await self.sandbox.communicate(f"mkdir -p {full_path}")
        if exit_code != 0:
            raise OSError(f"Couldn't create directory: {full_path}")

    async def write(self, path: str, content: Union[str, bytes]):
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
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

    async def exists(self, path: str) -> bool:
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
        result, exit_code = await self.sandbox.communicate(
            f"[ -e {full_path} ] && echo 'exists' || echo 'not exists'"
        )
        return exit_code == 0 and "exists" == result

    async def is_file(self, path: str) -> bool:
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
        result, exit_code = await self.sandbox.communicate(
            f"[ -f {full_path} ] && echo 'is file' || echo 'not file'"
        )
        return exit_code == 0 and "is file" == result

    async def is_dir(self, path: str) -> bool:
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
        result, exit_code = await self.sandbox.communicate(
            f"[ -d {full_path} ] && echo 'is dir' || echo 'not dir'"
        )
        return exit_code == 0 and "is dir" == result

    async def get_size(self, path: str) -> int:
        full_path = os.path.join(self.persistent_root, path.lstrip("/"))
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
        return Watcher(self, path)

    # async def watch_dir(self, path: str, callback):
    #     logger.info(f"Starting to watch directory: {path}")
    #     full_path = os.path.join(self.persistent_root, path.lstrip("/"))
    #     logger.debug(f"Full path to watch: {full_path}")

    #     # Ensure the directory exists
    #     if not await self.exists(path):
    #         logger.info(f"Directory {path} does not exist. Creating it.")
    #         await self.make_dir(path)

    #     initial_files = set(await self.list(path))
    #     logger.info(f"Initial files in {path}: {initial_files}")

    #     try:
    #         while True:
    #             await asyncio.sleep(1)
    #             logger.debug(f"Checking for changes in {path}")
    #             current_files = set(await self.list(path))

    #             # Check for new files
    #             new_files = current_files - initial_files
    #             for file in new_files:
    #                 logger.info(f"New file detected: {file}")
    #                 await callback("created", os.path.join(path, file))

    #             # Check for deleted files
    #             deleted_files = initial_files - current_files
    #             for file in deleted_files:
    #                 logger.info(f"File deleted: {file}")
    #                 await callback("deleted", os.path.join(path, file))

    #             if new_files or deleted_files:
    #                 logger.info(f"Updated file list: {current_files}")

    #             initial_files = current_files
    #     except asyncio.CancelledError:
    #         logger.info(f"Stopped watching directory: {path}")
