import asyncio
import pytest
import aiohttp
from firebox.api.sandbox_api import SandboxesApi
from firebox.api.models import NewSandbox


@pytest.mark.asyncio
async def test_sandbox_creation_and_custom_image():
    api = SandboxesApi()

    try:
        # Define a custom Dockerfile for a simple Flask app
        dockerfile = """
        FROM python:3.9-slim
        RUN pip install flask
        WORKDIR /app
        COPY . /app
        RUN echo 'from flask import Flask\n\
app = Flask(__name__)\n\
\n\
@app.route("/")\n\
def hello():\n\
    return "Hello from Firebox!"\n\
\n\
if __name__ == "__main__":\n\
    app.run(host="0.0.0.0", port=5000)' > /app/app.py
        CMD ["python", "app.py"]
        """

        # Create a new sandbox with a custom image
        new_sandbox = NewSandbox(
            template_id="firebox-test-flask-app",
            dockerfile=dockerfile,
            cpu_count=1,
            memory_mb=512,
            ports={"5000": 5000},
        )

        # Create the sandbox
        sandbox = await api.sandboxes_post(new_sandbox)
        assert sandbox.sandbox_id is not None
        assert sandbox.template_id == "firebox-test-flask-app"

        # Wait for the container to start and the app to be ready
        await asyncio.sleep(5)

        # Test the Flask app
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:5000") as response:
                assert response.status == 200
                text = await response.text()
                assert text == "Hello from Firebox!"

        # Check sandbox health
        health = await api.check_sandbox_health(sandbox.sandbox_id)
        assert health["status"] == "healthy" or health["status"] == "starting"
        assert health["running"] == True

        # Get sandbox stats
        stats = await api.get_sandbox_stats(sandbox.sandbox_id)
        assert "cpu_usage" in stats
        assert "memory_usage" in stats
        assert "network_rx" in stats
        assert "network_tx" in stats

        # List running sandboxes
        sandboxes = await api.sandboxes_get()
        assert any(s.sandbox_id == sandbox.sandbox_id for s in sandboxes)

        # Get sandbox logs
        logs = await api.sandboxes_sandbox_id_logs_get(sandbox.sandbox_id)
        assert any("Running on http://0.0.0.0:5000" in log.line for log in logs.logs)

    finally:
        # Clean up
        if sandbox:
            await api.sandboxes_sandbox_id_delete(sandbox.sandbox_id)
        await api.close()


@pytest.mark.asyncio
async def test_sandbox_file_operations():
    api = SandboxesApi()

    try:
        # Create a new sandbox with a basic image
        new_sandbox = NewSandbox(
            template_id="ubuntu:latest", cpu_count=1, memory_mb=256
        )

        sandbox = await api.sandboxes_post(new_sandbox)
        assert sandbox.sandbox_id is not None

        # Test file upload
        test_content = "Hello, Firebox!"
        await api.upload_file(
            sandbox.sandbox_id, test_content.encode(), "/tmp/test.txt"
        )

        # Test file download
        downloaded_content = await api.download_file(
            sandbox.sandbox_id, "/tmp/test.txt"
        )
        assert downloaded_content.decode() == test_content

        # Test file listing
        files = await api.list_files(sandbox.sandbox_id, "/tmp")
        assert "test.txt" in [file.name for file in files]

    finally:
        # Clean up
        if sandbox:
            await api.sandboxes_sandbox_id_delete(sandbox.sandbox_id)
        await api.close()


if __name__ == "__main__":
    pytest.main(["-v", "test_integration.py"])
