import pytest
import asyncio
from firebox.docker_sandbox import Sandbox
from firebox.models import SandboxConfig, ProcessMessage
from firebox.config import config
from firebox.logs import logger
from firebox.exception import TimeoutException


@pytest.fixture(scope="function")
def sandbox_config(tmp_path):
    logger.info("Creating sandbox configuration")
    persistent_storage_path = tmp_path / "persistent_storage"
    persistent_storage_path.mkdir(exist_ok=True)
    sandbox_conf = SandboxConfig(
        image=config.sandbox_image,
        cpu=config.cpu,
        memory=config.memory,
        environment={"TEST_ENV": "test_value"},
        persistent_storage_path=str(persistent_storage_path),
        cwd="/sandbox",
    )
    logger.info(f"Sandbox configuration created: {sandbox_conf}")
    return sandbox_conf


@pytest.fixture(scope="function")
async def sandbox(sandbox_config):
    logger.info("Initializing sandbox")
    s = Sandbox(sandbox_config)
    await s.init()
    logger.info(f"Sandbox initialized with ID: {s.id}")
    yield s
    logger.info(f"Closing sandbox with ID: {s.id}")
    await s.close()


@pytest.mark.asyncio
async def test_process_start(sandbox):
    logger.info("Starting test_process_start")
    running_process = await sandbox.process.start("echo 'Hello, World!'")
    logger.info(f"Process started with PID: {running_process.pid}")
    assert running_process.pid > 0

    logger.info("Waiting for process to complete")
    result = await running_process.wait(timeout=5)
    logger.info(f"Process completed. Result: {result}")
    assert result["stdout"].strip() == "Hello, World!"
    assert result["exit_code"] == 0

    is_running = await running_process.is_running()
    logger.info(f"Process running status: {is_running}")
    assert not is_running


@pytest.mark.asyncio
async def test_process_start_with_env_and_cwd(sandbox):
    logger.info("Starting test_process_start_with_env_and_cwd")
    running_process = await sandbox.process.start(
        "echo $TEST_VAR && pwd", env_vars={"TEST_VAR": "test_value"}, cwd="/tmp"
    )
    logger.info(f"Process started with PID: {running_process.pid}")

    result = await running_process.wait()
    logger.info(f"Process completed. Result: {result}")
    assert "test_value" in result["stdout"]
    assert "/tmp" in result["stdout"]
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_process_list(sandbox):
    logger.info("Starting test_process_list")
    running_process = await sandbox.process.start("sleep 2")
    logger.info(f"Started sleep process with PID: {running_process.pid}")

    processes = await sandbox.process.list()
    logger.info(f"Process list: {processes}")

    assert len(processes) > 0
    assert any(str(running_process.pid) == str(p["pid"]) for p in processes)

    await running_process.wait()
    logger.info("Sleep process completed")


@pytest.mark.asyncio
async def test_process_get(sandbox):
    logger.info("Starting test_process_get")
    running_process = await sandbox.process.start("sleep 2")
    logger.info(f"Started sleep process with PID: {running_process.pid}")

    retrieved_process = await sandbox.process.get(running_process.pid)
    logger.info(f"Retrieved process: {retrieved_process}")

    assert retrieved_process is not None
    assert retrieved_process.pid == running_process.pid

    await running_process.wait()
    logger.info("Sleep process completed")


@pytest.mark.asyncio
async def test_process_send_stdin(sandbox):
    logger.info("Starting test_process_send_stdin")
    running_process = await sandbox.process.start("cat")
    logger.info(f"Started cat process with PID: {running_process.pid}")

    await running_process.send_stdin("Hello, stdin!")
    logger.info("Sent 'Hello, stdin!' to the process")
    await asyncio.sleep(1)

    await running_process.kill()
    logger.info("Killed the cat process")

    result = await running_process.get_result()
    logger.info(f"Process result: {result}")
    assert "Hello, stdin!" in result["stdout"]


@pytest.mark.asyncio
async def test_process_on_exit(sandbox):
    logger.info("Starting test_process_on_exit")
    exit_called = False
    exit_code = None

    def on_exit(code: int):
        nonlocal exit_called, exit_code
        exit_called = True
        exit_code = code
        logger.info(f"Exit callback called with code: {code}")

    running_process = await sandbox.process.start("echo 'Test'", on_exit=on_exit)
    logger.info(f"Started echo process with PID: {running_process.pid}")

    await running_process.wait()
    logger.info("Process completed")

    assert exit_called, "Exit callback was not called"
    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"


@pytest.mark.asyncio
async def test_multiple_processes(sandbox):
    logger.info("Starting test_multiple_processes")
    process1 = await sandbox.process.start("echo 'Process 1'")
    logger.info(f"Started process 1 with PID: {process1.pid}")
    process2 = await sandbox.process.start("echo 'Process 2'")
    logger.info(f"Started process 2 with PID: {process2.pid}")

    result1 = await process1.wait()
    logger.info(f"Process 1 completed. Result: {result1}")
    result2 = await process2.wait()
    logger.info(f"Process 2 completed. Result: {result2}")

    assert "Process 1" in result1["stdout"]
    assert "Process 2" in result2["stdout"]


@pytest.mark.asyncio
async def test_process_stream_output(sandbox):
    logger.info("Starting test_process_stream_output")
    output = []

    def on_stdout(message: ProcessMessage):
        logger.debug(f"Received output: {message}")
        output.append(message.line.strip())

    running_process = await sandbox.process.start(
        "echo 'Line 1' && sleep 1 && echo 'Line 2'", on_stdout=on_stdout
    )
    logger.info(f"Started process with PID: {running_process.pid}")

    await running_process.wait()
    logger.info("Process completed")
    await asyncio.sleep(2)  # Give some time for the output to be processed

    logger.info(f"Collected output: {output}")
    assert len(output) == 2, f"Expected 2 lines of output, got {len(output)}"
    assert "Line 1" in output[0], f"Expected 'Line 1' in first output, got {output[0]}"
    assert "Line 2" in output[1], f"Expected 'Line 2' in second output, got {output[1]}"


@pytest.mark.asyncio
async def test_process_kill(sandbox):
    logger.info("Starting test_process_kill")
    running_process = await sandbox.process.start("sleep 10")
    logger.info(f"Started sleep process with PID: {running_process.pid}")
    await asyncio.sleep(0.5)  # Give some time for the process to start

    is_running = await running_process.is_running()
    logger.info(f"Process running status before kill: {is_running}")
    assert is_running, "Process should be running before kill"

    await running_process.kill()
    logger.info("Sent kill signal to the process")
    await asyncio.sleep(0.5)  # Give some time for the process to be killed

    is_running = await running_process.is_running()
    logger.info(f"Process running status after kill: {is_running}")
    process_status = await running_process._get_process_status()
    logger.info(f"Process status after kill: {process_status}")
    assert (
        not is_running
    ), f"Process should not be running after kill, status: {process_status}"


@pytest.mark.asyncio
async def test_process_timeout(sandbox):
    logger.info("Starting test_process_timeout")
    with pytest.raises(TimeoutException):
        running_process = await sandbox.process.start("sleep 10")
        logger.info(f"Started sleep process with PID: {running_process.pid}")
        logger.info("Process started, waiting with timeout")
        await running_process.wait(timeout=2)
    logger.info("TimeoutException raised as expected")


@pytest.mark.asyncio
async def test_long_running_process(sandbox):
    logger.info("Starting test_long_running_process")
    running_process = await sandbox.process.start("sleep 2 && echo 'Done'")
    logger.info(f"Started process with PID: {running_process.pid}")

    is_running = await running_process.is_running()
    logger.info(f"Process running status immediately after start: {is_running}")
    assert is_running, "Process should be running immediately after start"

    logger.info("Waiting for 3 seconds")
    await asyncio.sleep(3)
    is_running = await running_process.is_running()
    logger.info(f"Process running status after sleep: {is_running}")
    assert not is_running, "Process should not be running after sleep"

    result = await running_process.get_result()
    logger.info(f"Process result: {result}")
    assert (
        "Done" in result["stdout"]
    ), f"Expected 'Done' in output, got {result['stdout']}"


@pytest.mark.asyncio
async def test_process_in_persistent_storage(sandbox):
    logger.info("Starting test_process_in_persistent_storage")

    # Write a script to the persistent storage
    script_content = "#!/bin/bash\necho 'Hello from persistent storage!'"
    await sandbox.filesystem.write("test_script.sh", script_content)

    # Make the script executable
    await sandbox.communicate("chmod +x /sandbox/test_script.sh")

    # Run the script
    running_process = await sandbox.process.start("/sandbox/test_script.sh")
    result = await running_process.wait()

    logger.info(f"Process result: {result}")
    assert result["exit_code"] == 0
    assert "Hello from persistent storage!" in result["stdout"]
