import pytest
import asyncio
import os
from firebox.sandbox import Sandbox
from firebox.models.sandbox import DockerSandboxConfig
from firebox.models.filesystem import FilesystemOperation, FilesystemEvent
from firebox.config import config
from firebox.logs import logger


@pytest.fixture(scope="function")
def sandbox_config(tmp_path):
    persistent_storage_path = tmp_path / "persistent_storage"
    persistent_storage_path.mkdir(exist_ok=True)
    return DockerSandboxConfig(
        image=config.sandbox_image,
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
        persistent_storage_path=str(persistent_storage_path),
        cwd="/sandbox",
    )


@pytest.fixture
async def filesystem(sandbox_config):
    sandbox = await Sandbox.create(template=sandbox_config)
    yield sandbox.filesystem
    await sandbox.close()


@pytest.mark.asyncio
async def test_filesystem_write_read(filesystem):
    test_content = "Hello, FileSystem!"
    await filesystem.write("test.txt", test_content)
    content = await filesystem.read("test.txt")
    assert content == test_content


@pytest.mark.asyncio
async def test_filesystem_list(filesystem):
    await filesystem.write("test1.txt", "Test 1")
    await filesystem.write("test2.txt", "Test 2")
    files = await filesystem.list(".")
    assert any(file.name == "test1.txt" for file in files)
    assert any(file.name == "test2.txt" for file in files)


@pytest.mark.asyncio
async def test_filesystem_delete(filesystem):
    test_file = "to_delete.txt"
    await filesystem.write(test_file, "Delete me")
    assert await filesystem.exists(test_file)

    contents_before = await filesystem.list(".")
    logger.info(f"Contents before delete: {contents_before}")

    await filesystem.remove(test_file)

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
    await filesystem.write("test_file.txt", "Test content")
    assert await filesystem.is_file("test_file.txt")
    assert not await filesystem.is_file("non_existent_file.txt")


@pytest.mark.asyncio
async def test_filesystem_get_size(filesystem):
    test_content = "Hello, World!"
    await filesystem.write("size_test.txt", test_content)
    size = await filesystem.get_size("size_test.txt")
    expected_size = len(test_content.encode("utf-8")) + 1
    assert size == expected_size, f"Expected size {expected_size}, but got {size}"


@pytest.mark.asyncio
async def test_filesystem_watch_dir(filesystem):
    logger.info("Starting test_filesystem_watch_dir")
    events = []

    def event_listener(event: FilesystemEvent):
        logger.info(f"Event received: {event}")
        events.append(event)

    watcher = filesystem.watch_dir(".")
    watcher.add_event_listener(event_listener)
    await watcher.start()

    try:
        await asyncio.sleep(1)  # Wait for watcher to start

        test_file = "test_file.txt"
        logger.info(f"Writing file: {test_file}")
        await filesystem.write(test_file, "Hello, World!")

        await asyncio.sleep(2)  # Wait for events to be processed

        logger.info(f"Removing file: {test_file}")
        await filesystem.remove(test_file)

        await asyncio.sleep(2)  # Wait for events to be processed
    finally:
        await watcher.stop()

    logger.info(f"Events recorded: {events}")

    # Filter out any unexpected events
    relevant_events = [event for event in events if event.name == test_file]

    assert (
        len(relevant_events) == 2
    ), f"Expected 2 events for {test_file}, got {len(relevant_events)}"
    assert (
        relevant_events[0].operation == FilesystemOperation.Create
    ), f"Expected Create operation, got {relevant_events[0].operation}"
    assert (
        relevant_events[1].operation == FilesystemOperation.Remove
    ), f"Expected Remove operation, got {relevant_events[1].operation}"
    assert all(
        event.path.endswith(test_file) for event in relevant_events
    ), f"Unexpected file path in events"

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

    await filesystem.write_bytes(remote_path, test_content)

    exists = await filesystem.exists(remote_path)
    logger.info(f"Remote file exists: {exists}")
    assert exists, f"Remote file {remote_path} does not exist after upload"

    downloaded_content = await filesystem.read_bytes(remote_path)
    download_path.write_bytes(downloaded_content)

    logger.info(f"Downloaded content: {downloaded_content}")

    assert (
        downloaded_content == test_content
    ), "Downloaded content does not match original content"

    logger.info("Test completed successfully")
