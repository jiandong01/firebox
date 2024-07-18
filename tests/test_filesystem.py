import pytest
import asyncio
import os
from firebox.docker_sandbox import Sandbox
from firebox.models import SandboxConfig
from firebox.filesystem import Filesystem
from firebox.config import config
from firebox.logs import logger


@pytest.fixture(scope="function")
def sandbox_config(tmp_path):
    persistent_storage_path = tmp_path / "persistent_storage"
    persistent_storage_path.mkdir(exist_ok=True)
    return SandboxConfig(
        image=config.sandbox_image,
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
        persistent_storage_path=str(persistent_storage_path),
        cwd="/sandbox",
    )


@pytest.fixture
async def filesystem(sandbox_config):
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()
    await asyncio.sleep(2)  # Add a short delay to ensure the container is fully ready
    yield sandbox.filesystem
    await sandbox.close()


@pytest.mark.asyncio
async def test_filesystem_write_read(filesystem):
    test_content = b"Hello, FileSystem!"
    await filesystem.write("test.txt", test_content)
    content = await filesystem.read("test.txt")
    assert content == test_content


@pytest.mark.asyncio
async def test_filesystem_list(filesystem):
    await filesystem.write("test1.txt", b"Test 1")
    await filesystem.write("test2.txt", b"Test 2")
    files = await filesystem.list(".")
    assert "test1.txt" in files
    assert "test2.txt" in files


@pytest.mark.asyncio
async def test_filesystem_delete(filesystem):
    test_file = "to_delete.txt"

    await filesystem.write(test_file, b"Delete me")
    assert await filesystem.exists(test_file)

    contents_before = await filesystem.list(".")
    logger.info(f"Contents before delete: {contents_before}")

    await filesystem.delete(test_file)

    file_exists = await filesystem.exists(test_file)
    contents_after = await filesystem.list(".")

    logger.info(f"File {test_file} exists after delete: {file_exists}")
    logger.info(f"Contents after delete: {contents_after}")

    assert not file_exists, f"File {test_file} still exists after deletion"


@pytest.mark.asyncio
async def test_filesystem_make_dir(filesystem):
    await filesystem.make_dir("new_dir")
    assert await filesystem.is_dir("new_dir")


@pytest.mark.asyncio
async def test_filesystem_is_file(filesystem):
    await filesystem.write("test_file.txt", b"Test content")
    assert await filesystem.is_file("test_file.txt")
    assert not await filesystem.is_file("non_existent_file.txt")


@pytest.mark.asyncio
async def test_filesystem_get_size(filesystem):
    test_content = b"Hello, World!"
    await filesystem.write("size_test.txt", test_content)
    size = await filesystem.get_size("size_test.txt")
    assert size == len(test_content)


@pytest.mark.asyncio
async def test_filesystem_watch_dir(filesystem):
    logger.info("Starting test_filesystem_watch_dir")
    events = []

    def event_listener(event):
        logger.info(f"Event received: {event}")
        events.append(event)

    watcher = filesystem.watch_dir(".")
    watcher.add_event_listener(event_listener)
    watcher.start()

    try:
        await asyncio.sleep(1)

        test_file = "test_file.txt"
        logger.info(f"Writing file: {test_file}")
        await filesystem.write(test_file, b"Hello, World!")

        await asyncio.sleep(2)
    finally:
        await watcher.stop()

    logger.info(f"Events recorded: {events}")
    assert len(events) > 0, "No events were recorded"
    assert (
        events[0]["type"] == "created"
    ), f"Expected 'created' event, got {events[0]['type']}"
    assert events[0]["path"].endswith(
        test_file
    ), f"Expected path to end with {test_file}, got {events[0]['path']}"

    logger.info("test_filesystem_watch_dir completed successfully")


@pytest.mark.asyncio
async def test_filesystem_upload_download(filesystem, tmp_path):
    logger.info("Starting test_filesystem_upload_download")

    test_content = b"Test upload and download"
    local_path = tmp_path / "local_test.txt"
    remote_path = "remote_test.txt"
    download_path = tmp_path / "downloaded_test.txt"

    local_path.write_bytes(test_content)
    logger.info(f"Local file created with content: {test_content}")

    await filesystem.upload_file(str(local_path), remote_path)

    exists = await filesystem.exists(remote_path)
    logger.info(f"Remote file exists: {exists}")
    assert exists, f"Remote file {remote_path} does not exist after upload"

    await filesystem.download_file(remote_path, str(download_path))

    downloaded_content = download_path.read_bytes()
    logger.info(f"Downloaded content: {downloaded_content}")

    assert (
        downloaded_content == test_content
    ), "Downloaded content does not match original content"

    logger.info("Test completed successfully")
