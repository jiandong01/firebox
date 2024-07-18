# test_sandbox.py

import pytest
import docker
import os
from firebox.sandbox import Sandbox
from firebox.exceptions import TimeoutError
from firebox.config import config, SandboxConfig
from firebox.logs import logger


# Set the environment to 'test' for all tests
os.environ["FIREENV_ENVIRONMENT"] = "test"


@pytest.fixture(scope="module", autouse=True)
def docker_client():
    return docker.from_env()


@pytest.fixture(scope="module", autouse=True)
def cleanup_containers(docker_client):
    yield
    logger.info("Cleaning up containers and their associated volumes")
    for container in docker_client.containers.list(all=True):
        if container.name.startswith("sandbox_"):
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
        if volume.name.endswith("_volume"):
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
def sandbox_config():
    return SandboxConfig(
        image_name=config.fireenv.sandbox.image_name,
        cpu=config.fireenv.sandbox.cpu,
        memory=config.fireenv.sandbox.memory,
        container_prefix=config.fireenv.sandbox.container_prefix,
        persistent_storage_path=config.fireenv.sandbox.persistent_storage_path,
        timeout=config.fireenv.sandbox.timeout,
    )


@pytest.fixture(scope="function")
async def sandbox(sandbox_config):
    s = Sandbox(sandbox_config)
    await s.init()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_sandbox_init(sandbox):
    logger.info(f"Testing sandbox initialization with ID: {sandbox.id}")
    assert sandbox.id is not None
    assert sandbox.container is not None
    assert sandbox.container.status == "running"


@pytest.mark.asyncio
async def test_sandbox_communicate(sandbox):
    logger.info(f"Testing sandbox communication with ID: {sandbox.id}")
    result, exit_code = await sandbox.communicate("echo 'Hello, Sandbox!'")
    assert result.strip() == "Hello, Sandbox!"
    assert exit_code == 0


@pytest.mark.asyncio
async def test_sandbox_reconnect(sandbox_config):
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
async def test_sandbox_metadata(sandbox_config):
    logger.info("Testing sandbox metadata")
    sandbox_config.metadata = {"key": "value"}
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()
    assert sandbox.get_metadata("key") == "value"
    sandbox.set_metadata("new_key", "new_value")
    assert sandbox.get_metadata("new_key") == "new_value"
    await sandbox.close()


@pytest.mark.asyncio
async def test_sandbox_env_vars(sandbox_config):
    logger.info("Testing sandbox environment variables")
    sandbox_config.environment = {"TEST_VAR": "test_value"}
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()
    result, exit_code = await sandbox.communicate("echo $TEST_VAR")
    assert result.strip() == "test_value"
    assert exit_code == 0
    await sandbox.close()


@pytest.mark.asyncio
async def test_sandbox_timeout(sandbox):
    logger.info(f"Testing sandbox timeout with ID: {sandbox.id}")
    with pytest.raises(TimeoutError):
        await sandbox.communicate("sleep 10", timeout=1)


@pytest.mark.asyncio
async def test_sandbox_with_existing_id(sandbox_config):
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
async def test_sandbox_reuse(sandbox_config):
    logger.info("Testing sandbox reuse")
    sandbox1 = Sandbox(sandbox_config)
    await sandbox1.init()

    sandbox_config.sandbox_id = sandbox1.id
    sandbox2 = Sandbox(sandbox_config)
    await sandbox2.init()

    assert sandbox1.container.id == sandbox2.container.id

    await sandbox1.close()


@pytest.mark.asyncio
async def test_sandbox_cleanup(docker_client, sandbox_config):
    logger.info("Testing sandbox cleanup")
    sandbox = Sandbox(sandbox_config)
    await sandbox.init()

    assert sandbox.container is not None
    assert sandbox.container.status == "running"

    await sandbox.close()

    with pytest.raises(docker.errors.NotFound):
        docker_client.containers.get(f"sandbox_{sandbox.id}")

    with pytest.raises(docker.errors.NotFound):
        docker_client.volumes.get(f"{sandbox.id}_volume")
