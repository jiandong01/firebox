import pytest
import asyncio
import os
from firebox.docker_sandbox import Sandbox
from firebox.models.sandbox import SandboxConfig
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

    sandbox_config = SandboxConfig(
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
        sandbox = Sandbox(sandbox_config)
        await sandbox.init()

        assert sandbox.container.status == "running"

        result, exit_code = await sandbox.communicate(
            "python -c \"import requests; print('Test successful!')\""
        )

        assert exit_code == 0
        assert "Test successful!" in result

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

    sandbox_config = SandboxConfig(
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
        sandbox = Sandbox(sandbox_config)
        await sandbox.init()

        assert sandbox.container.status == "running"

        result, exit_code = await sandbox.communicate("cat /sandbox/test.txt")

        assert exit_code == 0
        assert "Hello from host!" in result

        logger.info("Custom Dockerfile sandbox with volume test passed successfully")
    except Exception as e:
        logger.error(f"Error in custom Dockerfile sandbox with volume test: {str(e)}")
        raise
    finally:
        if sandbox:
            await sandbox.close()
