import pytest
import asyncio
from firebox.sandbox import Sandbox
from firebox.models.sandbox import DockerSandboxConfig
from firebox.models.process import ProcessMessage, ProcessOutput, RunningProcess
from firebox.config import config
from firebox.logs import logger
from firebox.exception import TimeoutException


@pytest.fixture(scope="function")
def sandbox_config(tmp_path):
    logger.info("Creating sandbox configuration")
    persistent_storage_path = tmp_path / "persistent_storage"
    persistent_storage_path.mkdir(exist_ok=True)
    sandbox_conf = DockerSandboxConfig(
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
    s = await Sandbox.create(template=sandbox_config)
    logger.info(f"Sandbox initialized with ID: {s.id}")
    yield s
    logger.info(f"Closing sandbox with ID: {s.id}")
    await s.close()


@pytest.mark.asyncio
async def test_process_start(sandbox):
    logger.info("Starting test_process_start")
    process = await sandbox.process.start("echo 'Hello, World!'")
    logger.info(f"Process started with ID: {process._process_id}")

    logger.info("Waiting for process to complete")
    result = await process.wait(timeout=5)
    logger.info(f"Process completed. Result: {result}")
    assert "Hello, World!" in result.stdout
    assert result.exit_code == 0

    assert process._finished.done(), "Process should be finished"


@pytest.mark.asyncio
async def test_process_start_with_env_and_cwd(sandbox):
    logger.info("Starting test_process_start_with_env_and_cwd")
    process = await sandbox.process.start(
        "echo $TEST_VAR && pwd", env_vars={"TEST_VAR": "test_value"}, cwd="/tmp"
    )

    result = await process.wait()
    logger.info(f"Process completed. Result: {result}")
    assert "test_value" in result.stdout
    assert "/tmp" in result.stdout
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_process_send_stdin(sandbox):
    logger.info("Starting test_process_send_stdin")
    process = await sandbox.process.start(
        "cat",
        on_stdout=lambda msg: logger.info(f"Received output: {msg.line}"),
    )
    logger.info(f"Started process with ID: {process._process_id}")

    await process.send_stdin("AI Playground\n")
    logger.info("Sent 'AI Playground' to the process")
    await asyncio.sleep(2)  # Wait for the process to echo the input

    await process.kill()
    logger.info("Killed the process")

    result = await process.wait()
    logger.info(f"Process result: {result}")
    assert "AI Playground" in result.stdout


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

    process = await sandbox.process.start("echo 'Test'", on_exit=on_exit)
    logger.info(f"Started echo process with ID: {process._process_id}")

    await process.wait()
    logger.info("Process completed")

    assert exit_called, "Exit callback was not called"
    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"


@pytest.mark.asyncio
async def test_multiple_processes(sandbox):
    logger.info("Starting test_multiple_processes")
    process1 = await sandbox.process.start("echo 'Process 1'")
    logger.info(f"Started process 1 with ID: {process1._process_id}")
    process2 = await sandbox.process.start("echo 'Process 2'")
    logger.info(f"Started process 2 with ID: {process2._process_id}")

    result1 = await process1.wait()
    logger.info(f"Process 1 completed. Result: {result1}")
    result2 = await process2.wait()
    logger.info(f"Process 2 completed. Result: {result2}")

    assert "Process 1" in result1.stdout
    assert "Process 2" in result2.stdout


@pytest.mark.asyncio
async def test_process_stream_output(sandbox):
    logger.info("Starting test_process_stream_output")
    output = []

    def on_stdout(message: ProcessMessage):
        logger.debug(f"Received output: {message}")
        output.append(message.line.strip())

    process = await sandbox.process.start(
        "echo 'Line 1' && echo 'Line 2'", on_stdout=on_stdout
    )
    logger.info(f"Started process with ID: {process._process_id}")

    await process.wait()
    logger.info("Process completed")

    logger.info(f"Collected output: {output}")
    assert len(output) == 2, f"Expected 2 lines of output, got {len(output)}"
    assert "Line 1" in output[0], f"Expected 'Line 1' in first output, got {output[0]}"
    assert "Line 2" in output[1], f"Expected 'Line 2' in second output, got {output[1]}"


@pytest.mark.asyncio
async def test_process_kill(sandbox):
    logger.info("Starting test_process_kill")
    process = await sandbox.process.start("sleep 10")
    logger.info(f"Started sleep process with ID: {process._process_id}")
    await asyncio.sleep(0.5)  # Give some time for the process to start

    assert not process._finished.done(), "Process should be running before kill"

    await process.kill()
    logger.info("Sent kill signal to the process")
    await asyncio.sleep(0.5)  # Give some time for the process to be killed

    assert process._finished.done(), "Process should be finished after kill"


@pytest.mark.asyncio
async def test_process_timeout(sandbox):
    logger.info("Starting test_process_timeout")
    with pytest.raises(TimeoutException):
        process = await sandbox.process.start("sleep 10")
        logger.info(f"Started sleep process with ID: {process._process_id}")
        logger.info("Process started, waiting with timeout")
        await process.wait(timeout=2)
    logger.info("TimeoutException raised as expected")


@pytest.mark.asyncio
async def test_long_running_process(sandbox):
    logger.info("Starting test_long_running_process")
    process = await sandbox.process.start("sleep 2 && echo 'Done'")
    logger.info(f"Started process with ID: {process._process_id}")

    assert (
        not process._finished.done()
    ), "Process should be running immediately after start"

    logger.info("Waiting for 3 seconds")
    await asyncio.sleep(3)
    assert process._finished.done(), "Process should be finished after sleep"

    result = await process.wait()
    logger.info(f"Process result: {result}")
    assert "Done" in result.stdout, f"Expected 'Done' in output, got {result.stdout}"


@pytest.mark.asyncio
async def test_process_in_persistent_storage(sandbox):
    logger.info("Starting test_process_in_persistent_storage")

    # Write a script to the persistent storage
    script_content = "#!/bin/bash\necho 'Hello from persistent storage!'"
    await sandbox.filesystem.write("test_script.sh", script_content)

    # Make the script executable
    await sandbox.process.start_and_wait("chmod +x /sandbox/test_script.sh")

    # Run the script
    result = await sandbox.process.start_and_wait("/sandbox/test_script.sh")

    logger.info(f"Process result: {result}")
    assert result.exit_code == 0
    assert "Hello from persistent storage!" in result.stdout


@pytest.mark.asyncio
async def test_list_processes(sandbox):
    logger.info("Starting test_list_processes")

    # Start a long-running process
    long_process = await sandbox.process.start("sleep 10")
    logger.info(f"Started long-running process with ID: {long_process._process_id}")

    # Wait a bit to ensure the process is running
    await asyncio.sleep(1)

    # List processes
    processes = await sandbox.process.list_processes()
    logger.info(f"Listed processes: {processes}")

    # Check if our long-running process is in the list
    sleep_process_found = any("sleep 10" in p.cmd for p in processes)

    # Check for the main container process (usually 'tail -f /dev/null' or similar)
    main_process_found = any("tail -f /dev/null" in p.cmd for p in processes)

    if not sleep_process_found or not main_process_found:
        logger.error(f"Expected processes not found. All processes: {processes}")
        logger.error(
            f"Long process details: ID={long_process._process_id}, PID={long_process._pid}"
        )

        # Get more details about the running processes
        details = await sandbox.process.start_and_wait("ps aux")
        logger.error(f"Detailed process list:\n{details.stdout}")

        # Check if the sleep process is still running
        is_running = await sandbox.process.start_and_wait(f"ps -p {long_process._pid}")
        logger.error(
            f"Is long process still running? Exit code: {is_running.exit_code}"
        )

    assert (
        sleep_process_found
    ), "Long-running process (sleep 10) not found in process list"
    assert (
        main_process_found
    ), "Main container process (tail -f /dev/null) not found in process list"

    # Kill the long-running process
    await long_process.kill()
    await long_process.wait()

    logger.info("Test list_processes completed successfully")
