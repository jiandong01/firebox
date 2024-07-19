import pytest
import asyncio
import os
from firebox.sandbox import Sandbox
from firebox.models import DockerSandboxConfig
from firebox.config import config
from firebox.logs import logger


@pytest.fixture(scope="function")
def custom_dockerfile(tmp_path):
    dockerfile_content = """
    FROM python:3.9-slim
    RUN pip install requests
    WORKDIR /sandbox
    CMD ["python", "-c", "import requests; print('Custom sandbox is working!')"]
    """
    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text(dockerfile_content)
    return str(dockerfile_path)


@pytest.mark.asyncio
async def test_custom_dockerfile_sandbox(custom_dockerfile, tmp_path):
    logger.info(f"Testing sandbox with custom Dockerfile: {custom_dockerfile}")

    persistent_storage_path = tmp_path / "persistent_storage"
    persistent_storage_path.mkdir(exist_ok=True)

    sandbox_config = DockerSandboxConfig(
        image="custom-image",  # This will be overwritten by the Dockerfile
        dockerfile=custom_dockerfile,
        dockerfile_context=os.path.dirname(custom_dockerfile),
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
        persistent_storage_path=str(persistent_storage_path),
        cwd="/sandbox",
    )

    sandbox = None
    try:
        sandbox = await Sandbox.create(template=sandbox_config)

        assert sandbox._docker_sandbox.container is not None
        assert sandbox._docker_sandbox.container.status == "running"

        result = await sandbox.start_and_wait(
            "python -c \"import requests; print('Test successful!')\""
        )

        assert result.exit_code == 0
        assert "Test successful!" in result.stdout

        logger.info("Custom Dockerfile sandbox test passed successfully")
    except Exception as e:
        logger.error(f"Error in custom Dockerfile sandbox test: {str(e)}")
        raise
    finally:
        if sandbox:
            await sandbox.close()


@pytest.mark.asyncio
async def test_custom_dockerfile_sandbox_with_volume(custom_dockerfile, tmp_path):
    logger.info(
        f"Testing sandbox with custom Dockerfile and volume: {custom_dockerfile}"
    )

    persistent_storage_path = tmp_path / "persistent_storage"
    persistent_storage_path.mkdir(exist_ok=True)

    test_file = persistent_storage_path / "test.txt"
    test_file.write_text("Hello from host!")

    sandbox_config = DockerSandboxConfig(
        dockerfile=custom_dockerfile,
        dockerfile_context=os.path.dirname(custom_dockerfile),
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
        persistent_storage_path=str(persistent_storage_path),
        volumes={str(persistent_storage_path): {"bind": "/sandbox", "mode": "rw"}},
        cwd="/sandbox",
    )

    sandbox = None
    try:
        sandbox = await Sandbox.create(template=sandbox_config)

        assert sandbox._docker_sandbox.container is not None
        assert sandbox._docker_sandbox.container.status == "running"

        result = await sandbox.start_and_wait("cat /sandbox/test.txt")

        assert result.exit_code == 0
        assert "Hello from host!" in result.stdout

        logger.info("Custom Dockerfile sandbox with volume test passed successfully")
    except Exception as e:
        logger.error(f"Error in custom Dockerfile sandbox with volume test: {str(e)}")
        raise
    finally:
        if sandbox:
            await sandbox.close()
