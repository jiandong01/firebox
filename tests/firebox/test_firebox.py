import pytest
import docker
import os
from firebox.docker_sandbox import Sandbox
from firebox.exception import TimeoutException
from firebox.config import config, load_config
from firebox.models import SandboxConfig
from firebox.logs import logger

# Load test configuration
load_config("test_firebox_config.yaml")


@pytest.fixture(scope="module", autouse=True)
def docker_client():
    return docker.from_env()


@pytest.fixture(scope="module", autouse=True)
def cleanup_containers(docker_client):
    yield
    logger.info("Cleaning up containers and their associated volumes")
    for container in docker_client.containers.list(all=True):
        if container.name.startswith(config.container_prefix):
            logger.info(f"Removing container and its volumes: {container.name}")
            try:
                container.remove(v=True, force=True)
                logger.info(
                    f"Container {container.name} and its volumes removed successfully"
                )
            except docker.errors.NotFound:
                logger.warning(
                    f"Container {container.name} not found, it may have been already removed"
                )
            except Exception as e:
                logger.error(
                    f"Failed to remove container {container.name} and its volumes: {str(e)}"
                )

    # Check for any orphaned volumes
    for volume in docker_client.volumes.list():
        if volume.name.startswith(f"{config.container_prefix}_"):
            logger.warning(
                f"Orphaned volume found: {volume.name}. Attempting to remove."
            )
            try:
                volume.remove(force=True)
                logger.info(f"Orphaned volume {volume.name} removed successfully")
            except docker.errors.NotFound:
                logger.warning(
                    f"Volume {volume.name} not found, it may have been already removed"
                )
            except Exception as e:
                logger.error(
                    f"Failed to remove orphaned volume {volume.name}: {str(e)}"
                )


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


@pytest.fixture(scope="function")
async def sandbox(sandbox_config):
    s = Sandbox(sandbox_config)
    await s.init()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_firebox_init(sandbox):
    logger.info(f"Testing sandbox initialization with ID: {sandbox.id}")
    assert sandbox.id is not None
    assert sandbox.container is not None
    assert sandbox.container.status == "running"


@pytest.mark.asyncio
async def test_firebox_communicate(sandbox):
    logger.info(f"Testing sandbox communication with ID: {sandbox.id}")
    result, exit_code = await sandbox.communicate("echo 'Hello, Sandbox!'")
    assert result.strip() == "Hello, Sandbox!"
    assert exit_code == 0


@pytest.mark.asyncio
async def test_firebox_reconnect(sandbox_config):
    logger.info("Testing sandbox reconnection")
    original_sandbox = Sandbox(sandbox_config)
    await original_sandbox.init()
    sandbox_id = original_sandbox.id
    await original_sandbox.close()

    reconnected_sandbox = await Sandbox.reconnect(sandbox_id)
    assert reconnected_sandbox.id == sandbox_id
    result, exit_code = await reconnected_sandbox.communicate("echo 'reconnected'")
    assert result.strip() == "reconnected"
    assert exit_code == 0
    await reconnected_sandbox.close()


@pytest.mark.asyncio
async def test_firebox_metadata(sandbox_config):
    logger.info("Testing sandbox metadata")
    sandbox_config.metadata = {"key": "value"}
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()
    assert sandbox.get_metadata("key") == "value"
    sandbox.set_metadata("new_key", "new_value")
    assert sandbox.get_metadata("new_key") == "new_value"
    await sandbox.close()


@pytest.mark.asyncio
async def test_firebox_env_vars(sandbox):
    logger.info("Testing sandbox environment variables")
    result, exit_code = await sandbox.communicate("echo $TEST_ENV")
    assert result.strip() == "test_value"
    assert exit_code == 0


@pytest.mark.asyncio
async def test_firebox_timeout(sandbox):
    logger.info(f"Testing sandbox timeout with ID: {sandbox.id}")
    with pytest.raises(TimeoutException):
        await sandbox.communicate("sleep 10", timeout=1)


@pytest.mark.asyncio
async def test_firebox_with_existing_id(sandbox_config):
    logger.info("Testing sandbox with existing ID")
    existing_id = "test-existing-id"
    sandbox_config.sandbox_id = existing_id
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()
    assert sandbox.id == existing_id
    result, exit_code = await sandbox.communicate("echo 'Hello from existing ID'")
    assert result.strip() == "Hello from existing ID"
    assert exit_code == 0
    await sandbox.close()


@pytest.mark.asyncio
async def test_firebox_cwd(sandbox):
    logger.info("Testing sandbox current working directory")
    result, exit_code = await sandbox.communicate("pwd")
    assert result.strip() == "/sandbox"
    assert exit_code == 0

    sandbox.set_cwd("/tmp")
    result, exit_code = await sandbox.communicate("pwd")
    assert result.strip() == "/tmp"
    assert exit_code == 0


@pytest.mark.asyncio
async def test_firebox_volume(sandbox):
    logger.info("Testing sandbox volume mounting")

    # Create a test file in the persistent storage
    test_file = "test_volume.txt"
    test_content = "Hello from persistent storage!"
    await sandbox.filesystem.write(test_file, test_content)

    # Check if the file exists in the sandbox's working directory
    result, exit_code = await sandbox.communicate(f"cat {test_file}")

    assert (
        exit_code == 0
    ), f"Failed to read file. Exit code: {exit_code}, Result: {result}"
    assert (
        result.strip() == test_content
    ), f"File content mismatch. Expected: {test_content}, Got: {result.strip()}"

    # Verify the file exists in the persistent storage on the host
    host_file_path = os.path.join(sandbox.config.persistent_storage_path, test_file)
    assert os.path.exists(
        host_file_path
    ), f"File not found in host persistent storage: {host_file_path}"

    with open(host_file_path, "r") as f:
        host_content = f.read().strip()

    assert (
        host_content == test_content
    ), f"Host file content mismatch. Expected: {test_content}, Got: {host_content}"

    logger.info("Sandbox volume mounting test passed successfully")


@pytest.mark.asyncio
async def test_firebox_keep_alive(sandbox):
    logger.info("Testing sandbox keep alive")
    await sandbox.keep_alive(5000)  # Keep alive for 5 seconds
    assert sandbox.container.status == "running"


@pytest.mark.asyncio
async def test_firebox_list(sandbox):
    logger.info("Testing sandbox list")
    sandboxes = await Sandbox.list()
    assert len(sandboxes) > 0
    assert any(s["sandbox_id"] == sandbox.id for s in sandboxes)


@pytest.mark.asyncio
async def test_firebox_cleanup(docker_client, sandbox_config):
    logger.info("Testing sandbox cleanup")
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()

    assert sandbox.container is not None
    assert sandbox.container.status == "running"

    await sandbox.close()

    with pytest.raises(docker.errors.NotFound):
        docker_client.containers.get(f"{config.container_prefix}_{sandbox.id}")
