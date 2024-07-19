import base64
import logging
from typing import List, Optional

from firebox.constants import TIMEOUT
from firebox.exception import FilesystemException
from firebox.utils.filesystem import resolve_path
from firebox.filesystem.watcher import Watcher
from firebox.models import FileInfo

logger = logging.getLogger(__name__)


class FilesystemManager:
    """
    Manager for interacting with the filesystem in the sandbox.
    """

    def __init__(self, sandbox):
        self._sandbox = sandbox

    @property
    def cwd(self) -> Optional[str]:
        return self._sandbox.cwd

    async def read_bytes(self, path: str, timeout: Optional[float] = TIMEOUT) -> bytes:
        """
        Read the whole content of a file as a byte array.
        This can be used when you cannot represent the data as an UTF-8 string.

        :param path: path to a file
        :param timeout: timeout for the call
        :return: byte array representing the content of a file
        """
        path = resolve_path(path, self.cwd)
        try:
            exit_code, output = await self._sandbox.communicate(
                f"base64 {path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to read file: {output}")
            return base64.b64decode(output)
        except Exception as e:
            raise FilesystemException(
                f"Failed to read bytes from {path}: {str(e)}"
            ) from e

    async def write_bytes(
        self, path: str, content: bytes, timeout: Optional[float] = TIMEOUT
    ) -> None:
        """
        Write content to a file as a byte array.
        This can be used when you cannot represent the data as an UTF-8 string.

        A new file will be created if it doesn't exist.
        If the file already exists, it will be overwritten.

        :param path: path to a file
        :param content: byte array representing the content to write
        :param timeout: timeout for the call
        """
        path = resolve_path(path, self.cwd)
        base64_content = base64.b64encode(content).decode("utf-8")
        try:
            exit_code, output = await self._sandbox.communicate(
                f"echo '{base64_content}' | base64 -d > {path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to write file: {output}")
        except Exception as e:
            raise FilesystemException(
                f"Failed to write bytes to {path}: {str(e)}"
            ) from e

    async def read(self, path: str, timeout: Optional[float] = TIMEOUT) -> str:
        """
        Read the whole content of a file as a string.

        :param path: Path to a file
        :param timeout: Timeout for the operation
        :return: Content of a file
        """
        logger.debug(f"Reading file {path}")
        path = resolve_path(path, self.cwd)
        try:
            exit_code, output = await self._sandbox.communicate(
                f"cat {path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to read file: {output}")
            logger.debug(f"Read file {path}")
            return output
        except Exception as e:
            raise FilesystemException(f"Failed to read file {path}: {str(e)}") from e

    async def write(
        self, path: str, content: str, timeout: Optional[float] = TIMEOUT
    ) -> None:
        """
        Write content to a file.

        A new file will be created if it doesn't exist.
        If the file already exists, it will be overwritten.

        :param path: Path to a file
        :param content: Content to write
        :param timeout: Timeout for the operation
        """
        logger.debug(f"Writing file {path}")
        path = resolve_path(path, self.cwd)
        try:
            exit_code, output = await self._sandbox.communicate(
                f"echo '{content}' > {path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to write file: {output}")
            logger.debug(f"Wrote file {path}")
        except Exception as e:
            raise FilesystemException(
                f"Failed to write to file {path}: {str(e)}"
            ) from e

    async def remove(self, path: str, timeout: Optional[float] = TIMEOUT) -> None:
        """
        Remove a file or a directory.

        :param path: Path to a file or a directory
        :param timeout: Timeout for the operation
        """
        logger.debug(f"Removing file {path}")
        path = resolve_path(path, self.cwd)
        try:
            exit_code, output = await self._sandbox.communicate(
                f"rm -rf {path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to remove file: {output}")
            logger.debug(f"Removed file {path}")
        except Exception as e:
            raise FilesystemException(f"Failed to remove {path}: {str(e)}") from e

    async def list(
        self, path: str, timeout: Optional[float] = TIMEOUT
    ) -> List[FileInfo]:
        """
        List files in a directory.

        :param path: Path to a directory
        :param timeout: Timeout for the operation
        :return: Array of FileInfo objects representing files in a directory
        """
        logger.debug(f"Listing files in {path}")
        path = resolve_path(path, self.cwd)
        try:
            exit_code, output = await self._sandbox.communicate(
                f"ls -l {path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to list directory: {output}")
            logger.debug(f"Listed files in {path}, result: {output}")
            files = []
            for line in output.split("\n")[1:]:  # Skip the first line (total)
                parts = line.split()
                if len(parts) >= 9:
                    is_dir = parts[0].startswith("d")
                    name = " ".join(parts[8:])
                    files.append(FileInfo(is_dir=is_dir, name=name))
            return files
        except Exception as e:
            raise FilesystemException(
                f"Failed to list directory {path}: {str(e)}"
            ) from e

    async def make_dir(self, path: str, timeout: Optional[float] = TIMEOUT) -> None:
        """
        Create a new directory and all directories along the way if needed on the specified path.

        :param path: Path to a new directory
        :param timeout: Timeout for the operation
        """
        logger.debug(f"Creating directory {path}")
        path = resolve_path(path, self.cwd)
        try:
            exit_code, output = await self._sandbox.communicate(
                f"mkdir -p {path}", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to create directory: {output}")
            logger.debug(f"Created directory {path}")
        except Exception as e:
            raise FilesystemException(
                f"Failed to create directory {path}: {str(e)}"
            ) from e

    async def exists(self, path: str, timeout: Optional[float] = TIMEOUT) -> bool:
        """
        Check if a file or directory exists.

        :param path: Path to check
        :param timeout: Timeout for the operation
        :return: True if the path exists, False otherwise
        """
        path = resolve_path(path, self.cwd)
        try:
            exit_code, _ = await self._sandbox.communicate(
                f"test -e {path}", timeout=timeout
            )
            return exit_code == 0
        except Exception as e:
            raise FilesystemException(
                f"Failed to check existence of {path}: {str(e)}"
            ) from e

    async def is_file(self, path: str, timeout: Optional[float] = TIMEOUT) -> bool:
        """
        Check if a path is a file.

        :param path: Path to check
        :param timeout: Timeout for the operation
        :return: True if the path is a file, False otherwise
        """
        path = resolve_path(path, self.cwd)
        try:
            exit_code, _ = await self._sandbox.communicate(
                f"test -f {path}", timeout=timeout
            )
            return exit_code == 0
        except Exception as e:
            raise FilesystemException(
                f"Failed to check if {path} is a file: {str(e)}"
            ) from e

    async def is_dir(self, path: str, timeout: Optional[float] = TIMEOUT) -> bool:
        """
        Check if a path is a directory.

        :param path: Path to check
        :param timeout: Timeout for the operation
        :return: True if the path is a directory, False otherwise
        """
        path = resolve_path(path, self.cwd)
        try:
            exit_code, _ = await self._sandbox.communicate(
                f"test -d {path}", timeout=timeout
            )
            return exit_code == 0
        except Exception as e:
            raise FilesystemException(
                f"Failed to check if {path} is a directory: {str(e)}"
            ) from e

    async def get_size(self, path: str, timeout: Optional[float] = TIMEOUT) -> int:
        """
        Get the size of a file or directory.

        :param path: Path to get size for
        :param timeout: Timeout for the operation
        :return: Size in bytes
        """
        path = resolve_path(path, self.cwd)
        try:
            exit_code, output = await self._sandbox.communicate(
                f"du -sb {path} | cut -f1", timeout=timeout
            )
            if exit_code != 0:
                raise Exception(f"Failed to get size: {output}")
            return int(output.strip())
        except Exception as e:
            raise FilesystemException(f"Failed to get size of {path}: {str(e)}") from e

    def watch_dir(self, path: str) -> Watcher:
        """
        Watches directory for filesystem events.

        :param path: Path to a directory that will be watched
        :return: New watcher
        """
        logger.debug(f"Watching directory {path}")
        path = resolve_path(path, self.cwd)
        return Watcher(
            connection=self._sandbox,
            path=path,
            service_name="filesystem",
        )
