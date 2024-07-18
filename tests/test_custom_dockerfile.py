import pytest
import asyncio
import os
from firebox.sandbox import Sandbox
from firebox.models.sandbox import SandboxConfig
from firebox.config import config
from firebox.logs import logger


@pytest.fixture(scope="function")
def custom_dockerfile(tmp_path):
    dockerfile_content = """
    FROM python:3.9-slim
    RUN pip install requests
    WORKDIR /app
    CMD ["python", "-c", "import requests; print('Custom sandbox is working!')"]
    """
    dockerfile_path = tmp_path / "Dockerfile"
    dockerfile_path.write_text(dockerfile_content)
    return str(dockerfile_path)


@pytest.mark.asyncio
async def test_custom_dockerfile_sandbox(custom_dockerfile):
    logger.info(f"Testing sandbox with custom Dockerfile: {custom_dockerfile}")

    sandbox_config = SandboxConfig(
        dockerfile=custom_dockerfile,
        dockerfile_context=os.path.dirname(custom_dockerfile),
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
    )

    sandbox = None
    try:
        sandbox = Sandbox(sandbox_config)
        await sandbox.init()

        # Verify that the sandbox is running
        assert sandbox.container.status == "running"

        # Run a command to verify the custom image
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

    # Create a test file to be mounted
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello from host!")

    sandbox_config = SandboxConfig(
        dockerfile=custom_dockerfile,
        dockerfile_context=os.path.dirname(custom_dockerfile),
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
        volumes={str(tmp_path): {"bind": "/host", "mode": "ro"}},
    )

    sandbox = None
    try:
        sandbox = Sandbox(sandbox_config)
        await sandbox.init()

        # Verify that the sandbox is running
        assert sandbox.container.status == "running"

        # Check if the mounted file is accessible
        result, exit_code = await sandbox.communicate("cat /host/test.txt")

        assert exit_code == 0
        assert "Hello from host!" in result

        logger.info("Custom Dockerfile sandbox with volume test passed successfully")
    except Exception as e:
        logger.error(f"Error in custom Dockerfile sandbox with volume test: {str(e)}")
        raise
    finally:
        if sandbox:
            await sandbox.close()
