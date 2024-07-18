import pytest
import asyncio
import os
from firebox.sandbox import Sandbox, SandboxConfig, Filesystem
from firebox.config import config
from firebox.logs import logger


@pytest.fixture(scope="function")
def sandbox_config():
    return SandboxConfig(
        image_name=config.fireenv.sandbox.image_name,
        cpu=config.fireenv.sandbox.cpu,
        memory=config.fireenv.sandbox.memory,
        container_prefix=config.fireenv.sandbox.container_prefix,
        persistent_storage_path=config.fireenv.sandbox.persistent_storage_path,
        timeout=config.fireenv.sandbox.timeout,
    )


@pytest.fixture
async def filesystem(sandbox_config):
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()
    await asyncio.sleep(2)  # Add a short delay to ensure the container is fully ready
    filesystem = Filesystem(sandbox)
    yield filesystem
    await sandbox.close()


@pytest.mark.asyncio
async def test_filesystem_write_read(filesystem):
    test_content = b"Hello, FileSystem!"
    await filesystem.write("/tmp/test.txt", test_content)
    content = await filesystem.read("/tmp/test.txt")
    assert content == test_content


@pytest.mark.asyncio
async def test_filesystem_list(filesystem):
    await filesystem.write("/tmp/test1.txt", b"Test 1")
    await filesystem.write("/tmp/test2.txt", b"Test 2")
    files = await filesystem.list("/tmp")
    assert "test1.txt" in files
    assert "test2.txt" in files


@pytest.mark.asyncio
async def test_filesystem_delete(filesystem):
    test_file = "/tmp/to_delete.txt"

    # Write the file
    await filesystem.write(test_file, b"Delete me")
    assert await filesystem.exists(test_file)
    logger.info(f"File {test_file} created successfully.")

    # List contents before delete
    contents_before = await filesystem.list("/tmp")
    logger.info(f"Contents of /tmp before delete: {contents_before}")

    # Delete the file
    await filesystem.delete(test_file)
    logger.info(f"Delete operation completed for {test_file}")

    # Add a small delay to ensure filesystem operations are complete
    await asyncio.sleep(0.5)

    # Check if file exists and list contents after delete
    file_exists = await filesystem.exists(test_file)
    contents_after = await filesystem.list("/tmp")

    logger.info(f"File {test_file} exists after delete: {file_exists}")
    logger.info(f"Contents of /tmp after delete: {contents_after}")

    # Additional checks
    is_file = await filesystem.is_file(test_file)
    is_dir = await filesystem.is_dir(test_file)
    logger.info(f"Is {test_file} a file? {is_file}")
    logger.info(f"Is {test_file} a directory? {is_dir}")

    # Final assertion
    assert not file_exists, f"File {test_file} still exists after deletion"


@pytest.mark.asyncio
async def test_filesystem_make_dir(filesystem):
    await filesystem.make_dir("/tmp/new_dir")
    assert await filesystem.is_dir("/tmp/new_dir")


@pytest.mark.asyncio
async def test_filesystem_is_file(filesystem):
    await filesystem.write("/tmp/test_file.txt", b"Test content")
    assert await filesystem.is_file("/tmp/test_file.txt")
    assert not await filesystem.is_file("/tmp/non_existent_file.txt")


@pytest.mark.asyncio
async def test_filesystem_get_size(filesystem):
    test_content = b"Hello, World!"
    await filesystem.write("/tmp/size_test.txt", test_content)
    size = await filesystem.get_size("/tmp/size_test.txt")
    assert size == len(test_content)


@pytest.mark.asyncio
async def test_filesystem_watch_dir(filesystem):
    logger.info("Starting test_filesystem_watch_dir")
    events = []

    async def callback(event_type, file_path):
        logger.info(
            f"Callback called with event_type: {event_type}, file_path: {file_path}"
        )
        events.append((event_type, file_path))

    watch_task = asyncio.create_task(filesystem.watch_dir("/tmp", callback))
    logger.info("Watch task created")

    # Give some time for the watcher to start
    await asyncio.sleep(1)

    test_file = "/tmp/test_file.txt"
    logger.info(f"Writing file: {test_file}")
    await filesystem.write(test_file, b"Hello, World!")

    # Give some time for the watcher to detect the change
    await asyncio.sleep(2)

    logger.info("Cancelling watch task")
    watch_task.cancel()
    try:
        await watch_task
    except asyncio.CancelledError:
        logger.info("Watch task cancelled successfully")

    logger.info(f"Events recorded: {events}")
    assert len(events) > 0, "No events were recorded"
    assert events[0][0] == "created", f"Expected 'created' event, got {events[0][0]}"
    assert events[0][1] == test_file, f"Expected {test_file}, got {events[0][1]}"

    logger.info("test_filesystem_watch_dir completed successfully")


@pytest.mark.asyncio
async def test_filesystem_upload_download(filesystem):
    logger.info("Starting test_filesystem_upload_download")

    test_content = b"Test upload and download"
    local_path = "/tmp/local_test.txt"
    remote_path = "/tmp/remote_test.txt"
    download_path = "/tmp/downloaded_test.txt"

    logger.info(f"Creating local file: {local_path}")
    with open(local_path, "wb") as f:
        f.write(test_content)
    logger.info(f"Local file created with content: {test_content}")

    logger.info(f"Uploading file from {local_path} to {remote_path}")
    await filesystem.upload_file(local_path, remote_path)

    logger.info(f"Checking if remote file exists: {remote_path}")
    exists = await filesystem.exists(remote_path)
    logger.info(f"Remote file exists: {exists}")
    assert exists, f"Remote file {remote_path} does not exist after upload"

    logger.info(f"Downloading file from {remote_path} to {download_path}")
    await filesystem.download_file(remote_path, download_path)

    logger.info(f"Reading downloaded file: {download_path}")
    with open(download_path, "rb") as f:
        downloaded_content = f.read()
    logger.info(f"Downloaded content: {downloaded_content}")

    logger.info("Comparing original and downloaded content")
    assert (
        downloaded_content == test_content
    ), "Downloaded content does not match original content"

    # Clean up
    logger.info("Cleaning up local files")
    os.remove(local_path)
    os.remove(download_path)
    logger.info("Test completed successfully")
