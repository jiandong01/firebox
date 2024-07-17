import pytest
from unittest.mock import Mock, patch
from firebox.sandbox.filesystem import FilesystemManager, FileInfo
from firebox.sandbox.exception import FilesystemException


@pytest.fixture
def mock_sandbox_connection():
    return Mock()


@pytest.fixture
def filesystem_manager(mock_sandbox_connection):
    return FilesystemManager(mock_sandbox_connection)


def test_read_bytes(filesystem_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = "SGVsbG8="  # base64 for "Hello"
    result = filesystem_manager.read_bytes("/test/file.txt")
    assert result == b"Hello"
    mock_sandbox_connection._call.assert_called_with(
        "filesystem", "readBase64", ["/test/file.txt"], timeout=60
    )


def test_write_bytes(filesystem_manager, mock_sandbox_connection):
    filesystem_manager.write_bytes("/test/file.txt", b"Hello")
    mock_sandbox_connection._call.assert_called_with(
        "filesystem", "writeBase64", ["/test/file.txt", "SGVsbG8="], timeout=60
    )


def test_read(filesystem_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = "Hello"
    result = filesystem_manager.read("/test/file.txt")
    assert result == "Hello"
    mock_sandbox_connection._call.assert_called_with(
        "filesystem", "read", ["/test/file.txt"], timeout=60
    )


def test_write(filesystem_manager, mock_sandbox_connection):
    filesystem_manager.write("/test/file.txt", "Hello")
    mock_sandbox_connection._call.assert_called_with(
        "filesystem", "write", ["/test/file.txt", "Hello"], timeout=60
    )


def test_remove(filesystem_manager, mock_sandbox_connection):
    filesystem_manager.remove("/test/file.txt")
    mock_sandbox_connection._call.assert_called_with(
        "filesystem", "remove", ["/test/file.txt"], timeout=60
    )


def test_list(filesystem_manager, mock_sandbox_connection):
    mock_sandbox_connection._call.return_value = [
        {"isDir": True, "name": "dir1"},
        {"isDir": False, "name": "file1.txt"},
    ]
    result = filesystem_manager.list("/test")
    assert len(result) == 2
    assert isinstance(result[0], FileInfo)
    assert result[0].is_dir == True
    assert result[0].name == "dir1"
    assert result[1].is_dir == False
    assert result[1].name == "file1.txt"


def test_make_dir(filesystem_manager, mock_sandbox_connection):
    filesystem_manager.make_dir("/test/newdir")
    mock_sandbox_connection._call.assert_called_with(
        "filesystem", "makeDir", ["/test/newdir"], timeout=60
    )
