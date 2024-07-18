import time
import aiohttp
import socket
import asyncio
import pytest
from firebox.api.sandbox_api import SandboxesApi
from firebox.api.models import NewSandbox
from firebox.logging import logger
from firebox.exceptions import DockerOperationError


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.mark.asyncio
async def test_sandbox_creation_and_custom_image():
    api = SandboxesApi()
    sandbox = None

    try:
        free_port = find_free_port()

        # Define a custom Dockerfile for a simple Flask app
        dockerfile = f"""
FROM python:3.9-slim
RUN pip install flask
WORKDIR /app
COPY . /app
RUN echo 'import time\\n\
from flask import Flask\\n\
import logging\\n\
import sys\\n\
app = Flask(__name__)\\n\
logging.basicConfig(level=logging.INFO, stream=sys.stdout)\\n\
\\n\
@app.route("/")\\n\
def hello():\\n\
    app.logger.info("Received request")\\n\
    return "Hello from Firebox!"\\n\
\\n\
if __name__ == "__main__":\\n\
    app.logger.info(f"Starting Flask app on port {free_port}")\\n\
    time.sleep(5)  # Give some time for logs to be captured\\n\
    app.run(host="0.0.0.0", port={free_port})' > /app/app.py
CMD ["python", "app.py"]
"""

        # Create a new sandbox with a custom image
        new_sandbox = NewSandbox(
            template_id="firebox-test-flask-app",
            dockerfile=dockerfile,
            cpu_count=1,
            memory_mb=512,
            ports={f"{free_port}": free_port},
        )

        # Create the sandbox
        sandbox = await api.sandboxes_post(new_sandbox)
        assert sandbox.sandbox_id is not None
        assert sandbox.template_id == "firebox-test-flask-app"

        # Wait for the container to start and the app to be ready
        await asyncio.sleep(10)  # Increase the wait time further

        # Get the actual mapped port
        container_info = await api.get_container_info(sandbox.sandbox_id)
        actual_port = container_info["NetworkSettings"]["Ports"][f"{free_port}/tcp"][0][
            "HostPort"
        ]

        print(f"Container info: {container_info}")
        print(f"Actual port: {actual_port}")

        # Test the Flask app
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://localhost:{actual_port}") as response:
                assert response.status == 200
                text = await response.text()
                assert text == "Hello from Firebox!"

        # List running sandboxes
        sandboxes = await api.sandboxes_get()
        assert any(s.sandbox_id == sandbox.sandbox_id for s in sandboxes)

        # Get sandbox logs
        logs = await api.sandboxes_sandbox_id_logs_get(sandbox.sandbox_id)
        print("Sandbox logs:")
        for log in logs.logs:
            print(f"Timestamp: {log.timestamp}, Line: {log.line}")

        assert any(
            f"Starting Flask app on port {free_port}" in log.line for log in logs.logs
        ), "Flask app start message not found in logs"

        assert any(
            f"Running on http://127.0.0.1:{free_port}" in log.line for log in logs.logs
        ), f"Expected log message not found. Free port: {free_port}"

    except Exception as e:
        pytest.fail(f"Test failed with exception: {str(e)}")

    finally:
        # Clean up
        if sandbox:
            await api.sandboxes_sandbox_id_delete(sandbox.sandbox_id)
        await api.close()


async def wait_for_container_to_be_running(api, sandbox_id, max_retries=5, delay=2):
    for _ in range(max_retries):
        docker_adapter = await api._get_docker_adapter()
        container = await docker_adapter.client.containers.get(sandbox_id)
        info = await container.show()
        status = info["State"]["Status"]
        logger.info(f"Container status: {status}")
        if status == "running":
            return True
        await asyncio.sleep(delay)
    return False


@pytest.mark.asyncio
async def test_sandbox_file_operations():
    api = SandboxesApi()
    sandbox = None

    try:
        # Create a new sandbox with a basic image
        new_sandbox = NewSandbox(
            template_id="ubuntu:latest",
            cpu_count=1,
            memory_mb=256,
            ports={"8080": 8080},
            keep_alive=True,  # Ensure the container keeps running
            tty=True,  # Allocate a pseudo-TTY
        )

        sandbox = await api.sandboxes_post(new_sandbox)
        assert sandbox.sandbox_id is not None
        logger.info(f"Sandbox created with ID: {sandbox.sandbox_id}")

        # Wait for the container to start
        is_running = await wait_for_container_to_be_running(api, sandbox.sandbox_id)
        assert is_running, "Container failed to start within the expected time"

        # Test file upload
        test_content = "Hello, Firebox!"
        await api.upload_file(
            sandbox.sandbox_id, test_content.encode(), "/tmp/test.txt"
        )
        logger.info("File uploaded")

        # Test file listing
        max_retries = 3
        for attempt in range(max_retries):
            try:
                docker_adapter = await api._get_docker_adapter()

                # Check container status before executing command
                container = await docker_adapter.client.containers.get(
                    sandbox.sandbox_id
                )
                info = await container.show()
                logger.info(
                    f"Container status before listing files: {info['State']['Status']}"
                )

                if info["State"]["Status"] != "running":
                    raise DockerOperationError(
                        f"Container is not running. Status: {info['State']['Status']}"
                    )

                result = await docker_adapter.exec_command(
                    sandbox.sandbox_id, "ls -la /tmp"
                )
                logger.info(f"Files in /tmp: {result['output']}")
                assert (
                    "test.txt" in result["output"]
                ), f"test.txt not found in {result['output']}"
                break
            except DockerOperationError as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Failed to list files (attempt {attempt + 1}): {e}")
                await asyncio.sleep(2)

        # Test file download
        downloaded_content = await api.download_file(
            sandbox.sandbox_id, "/tmp/test.txt"
        )
        assert downloaded_content.decode() == test_content
        logger.info("File downloaded and content verified")

        # Test file removal
        await api.upload_file(
            sandbox.sandbox_id, b"This file will be removed", "/tmp/to_remove.txt"
        )
        result = await docker_adapter.exec_command(sandbox.sandbox_id, "ls -la /tmp")
        assert (
            "to_remove.txt" in result["output"]
        ), "to_remove.txt not found after upload"

        # Remove the file
        result = await docker_adapter.exec_command(
            sandbox.sandbox_id, "rm /tmp/to_remove.txt"
        )
        assert result["exit_code"] == 0, f"Failed to remove file: {result['output']}"

        # Verify file removal
        result = await docker_adapter.exec_command(sandbox.sandbox_id, "ls -la /tmp")
        assert (
            "to_remove.txt" not in result["output"]
        ), "to_remove.txt still present after removal"

    except Exception as e:
        logger.error(f"Test failed with exception: {str(e)}")

        # Additional error information
        if sandbox:
            try:
                docker_adapter = await api._get_docker_adapter()
                container = await docker_adapter.client.containers.get(
                    sandbox.sandbox_id
                )
                info = await container.show()
                logger.error(f"Container final status: {info['State']['Status']}")
                logger.error(f"Container state: {info['State']}")

                # Get container logs
                logs = await docker_adapter.get_sandbox_logs(sandbox.sandbox_id)
                logger.error(f"Container logs: {logs}")
            except Exception as log_e:
                logger.error(
                    f"Failed to get additional error information: {str(log_e)}"
                )

        pytest.fail(f"Test failed with exception: {str(e)}")

    finally:
        # Clean up
        if sandbox:
            try:
                await api.sandboxes_sandbox_id_delete(sandbox.sandbox_id)
                logger.info(f"Sandbox {sandbox.sandbox_id} deleted")
            except Exception as e:
                logger.error(f"Failed to delete sandbox: {str(e)}")
        await api.close()
