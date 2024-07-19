import pytest
import docker
import asyncio
import os
from firebox.sandbox import Sandbox
from firebox.exception import TimeoutException, SandboxException
from firebox.config import config
from firebox.models import DockerSandboxConfig, SandboxStatus
from firebox.logs import logger


@pytest.fixture(scope="module", autouse=True)
def docker_client():
    return docker.from_env()


@pytest.fixture(scope="module", autouse=True)
def cleanup_containers(docker_client):
    yield
    logger.info("Cleaning up containers and their associated volumes")
    for container in docker_client.containers.list(all=True):
        if container.name.startswith("firebox-sandbox_"):
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
        if volume.name.startswith("firebox-sandbox_"):
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
    return DockerSandboxConfig(
        image=config.sandbox_image,
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
        persistent_storage_path=str(persistent_storage_path),
        cwd="/sandbox",
    )


@pytest.fixture(scope="function")
async def sandbox(sandbox_config):
    s = await Sandbox.create(template=sandbox_config)
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_firebox_init(sandbox):
    logger.info(f"Testing sandbox initialization with ID: {sandbox.id}")
    assert sandbox.id is not None
    assert sandbox._docker_sandbox.container is not None
    assert sandbox._docker_sandbox.container.status == "running"
    assert sandbox.status == SandboxStatus.RUNNING


@pytest.mark.asyncio
async def test_firebox_communicate(sandbox):
    logger.info(f"Testing sandbox communication with ID: {sandbox.id}")
    result = await sandbox.process.start_and_wait("echo 'Hello, Sandbox!'")
    assert result.stdout.strip() == "Hello, Sandbox!"
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_firebox_reconnect(sandbox_config):
    logger.info("Testing sandbox reconnection")
    original_sandbox = await Sandbox.create(template=sandbox_config)
    sandbox_id = original_sandbox.id
    await original_sandbox.close()

    # Wait a bit to ensure the sandbox is fully closed
    await asyncio.sleep(1)

    reconnected_sandbox = await Sandbox.reconnect(sandbox_id)
    assert reconnected_sandbox.id == sandbox_id
    assert reconnected_sandbox.status == SandboxStatus.RUNNING
    result = await reconnected_sandbox.process.start_and_wait("echo 'reconnected'")
    assert result.stdout.strip() == "reconnected"
    assert result.exit_code == 0
    await reconnected_sandbox.close()


@pytest.mark.asyncio
async def test_firebox_env_vars(sandbox):
    logger.info("Testing sandbox environment variables")
    result = await sandbox.process.start_and_wait("echo $TEST_ENV")
    assert result.stdout.strip() == "test_value"
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_firebox_timeout(sandbox):
    logger.info(f"Testing sandbox timeout with ID: {sandbox.id}")
    with pytest.raises(TimeoutException):
        await sandbox.process.start_and_wait("sleep 10", timeout=1)


@pytest.mark.asyncio
async def test_firebox_cwd(sandbox):
    logger.info("Testing sandbox current working directory")
    result = await sandbox.process.start_and_wait("pwd")
    assert result.stdout.strip() == "/sandbox"

    new_cwd = "/tmp/test_dir"
    await sandbox.process.start_and_wait(f"mkdir -p {new_cwd}")
    sandbox.cwd = new_cwd
    result = await sandbox.process.start_and_wait("pwd")
    assert result.stdout.strip() == new_cwd


@pytest.mark.asyncio
async def test_firebox_volume(sandbox):
    logger.info("Testing sandbox volume mounting")

    # Create a test file in the persistent storage
    test_file = "test_volume.txt"
    test_content = "Hello from persistent storage!"
    await sandbox.filesystem.write(test_file, test_content)

    # Check if the file exists in the sandbox's working directory
    result = await sandbox.process.start_and_wait(f"cat {test_file}")

    assert result.exit_code == 0, f"Failed to read file. Result: {result}"
    assert (
        result.stdout.strip() == test_content
    ), f"File content mismatch. Expected: {test_content}, Got: {result.stdout.strip()}"

    # Verify the file exists in the persistent storage on the host
    host_file_path = os.path.join(
        sandbox._docker_sandbox.config.persistent_storage_path, test_file
    )
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
    await sandbox.keep_alive(5)  # Keep alive for 5 seconds
    assert sandbox._docker_sandbox.is_running()


@pytest.mark.asyncio
async def test_firebox_list(sandbox):
    logger.info("Testing sandbox list")
    sandboxes = Sandbox.list(include_closed=True)
    assert len(sandboxes) > 0, f"Expected at least 1 sandbox, got {len(sandboxes)}"
    assert any(
        s.sandbox_id == sandbox.id for s in sandboxes
    ), f"Sandbox {sandbox.id} not found in {sandboxes}"


@pytest.mark.asyncio
async def test_firebox_cleanup(docker_client, sandbox_config):
    logger.info("Testing sandbox cleanup")
    sandbox = await Sandbox.create(template=sandbox_config)

    assert sandbox._docker_sandbox.container is not None
    assert sandbox._docker_sandbox.is_running()

    await sandbox.close()
    assert sandbox.status == SandboxStatus.CLOSED

    await sandbox.release()
    assert sandbox.status == SandboxStatus.RELEASED

    with pytest.raises(docker.errors.NotFound):
        docker_client.containers.get(f"firebox-sandbox_{sandbox.id}")

    # Attempt to reconnect to a released sandbox should fail
    with pytest.raises(SandboxException):
        await Sandbox.reconnect(sandbox.id)
